"""Core chat handler — message matching and processing pipeline."""

import re

from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.rule import to_me

from src.config import config

from .llm_client import ChatAPIError, LLMClient
from .rate_limiter import rate_limiter
from .session_manager import session_manager

# ------------------------------------------------------------------
# Prompt-injection detection (basic safety net)
# ------------------------------------------------------------------

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|the\s+above|your)\s+(conversation|context|instructions?|prompt|rules?)",
    r"disregard\s+(previous|prior|your)\s+(instructions?|context|prompt)",
    r"forget\s+(everything|your|the)\s+(above|before|previous)",
    r"(new|follow|these)\s+(requirements?|instructions?|rules?)\s+(below|now|instead)",
    r"(answer|respond)\s+only\s+(based\s+on|to)\s+the\s+(new\s+)?",
    r"you\s+are\s+now\s+(a\s+|an\s+)?\w",
    r"act\s+as\s+(a\s+|an\s+)?\w",
    r"(system\s?prompt|override|jailbreak)",
    r"(write|output|generate|provide)\s+(a\s+|the\s+)?(complete\s+)?(code|program|script|python)",
    r"(role\s*play|pretend|imagine)\s+(you\s+are|to\s+be)",
    r"你\s*(现在|从现在开始)\s*(是|扮演|变成)",
    r"(忽略|忘记|无视)\s*(之前|前面|上面|以前|刚才)\s*(的|所有)?\s*(对话|指令|上下文|规则|提示|设定)",
    r"(只\s*根据|只\s*按照|只\s*响应)\s*(下面|以下|新的)",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def _detect_injection(text: str) -> bool:
    """Return True if the message looks like a prompt-injection attempt."""
    return bool(_INJECTION_RE.search(text))


# ------------------------------------------------------------------
# Matchers
# ------------------------------------------------------------------

from nonebot.rule import Rule, to_me


def _group_rule():
    """Group chat rule based on TRIGGER_MODE config.

    at_only  — respond only when @mentioned
    prefix   — respond when message starts with CHAT_PREFIX (default /chat)
    """
    if config.trigger_mode == "prefix":

        async def _prefix_checker(event: GroupMessageEvent) -> bool:
            text = event.get_plaintext().strip()
            return text.startswith(config.chat_prefix)

        return Rule(_prefix_checker)

    # Default: at_only
    return to_me()


# Private chat: respond to all messages
private_chat = on_message(
    priority=10,
    block=True,
)

# Group chat: respond based on trigger_mode
group_chat = on_message(
    rule=_group_rule(),
    priority=10,
    block=True,
)

# Reset command: /reset or /clear
reset_cmd = on_command(
    "reset",
    priority=5,
    block=True,
    aliases={"clear", "新对话", "重置"},
)

# ------------------------------------------------------------------
# LLM client instance
# ------------------------------------------------------------------
llm_client = LLMClient()

# Maximum length per QQ message (leave some margin below the ~5000 limit)
MAX_MSG_LENGTH = 4000


# ------------------------------------------------------------------
# Event handlers
# ------------------------------------------------------------------
@private_chat.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent) -> None:
    """Handle private chat messages — respond to everything."""
    user_id = str(event.user_id)
    message_text = event.get_plaintext().strip()

    if not message_text:
        return

    await _process_message(
        bot=bot,
        session_id=user_id,
        message_text=message_text,
        event=event,
    )


def _get_sender_name(event: GroupMessageEvent) -> str:
    """Get the best display name for a group message sender."""
    card = event.sender.card or ""
    nickname = event.sender.nickname or ""
    return card or nickname or str(event.user_id)


@group_chat.handle()
async def handle_group(bot: Bot, event: GroupMessageEvent) -> None:
    """Handle group chat messages — respond when @mentioned."""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    message_text = event.get_plaintext().strip()

    if not message_text:
        return

    # Label the message with sender's name and QQ so the LLM knows who's talking
    sender = _get_sender_name(event)
    labeled_text = f"[{sender}](QQ:{user_id}): {message_text}"

    # Use group-level session (shared context among group members)
    await _process_message(
        bot=bot,
        session_id=group_id,
        message_text=labeled_text,
        event=event,
    )


@reset_cmd.handle()
async def handle_reset(
    bot: Bot, event: MessageEvent, args=CommandArg()
) -> None:
    """Handle /reset command — clear conversation history."""
    user_id = str(event.user_id)

    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        session_manager.reset_session(group_id)
        await reset_cmd.finish(
            MessageSegment.reply(event.message_id) + "Conversation history cleared."
        )
    else:
        session_manager.reset_session(user_id)
        await reset_cmd.finish(
            MessageSegment.reply(event.message_id) + "Your conversation history has been cleared."
        )


# ------------------------------------------------------------------
# Processing pipeline
# ------------------------------------------------------------------
async def _process_message(
    bot: Bot,
    session_id: str,
    message_text: str,
    event: MessageEvent,
) -> None:
    """Message processing pipeline — rate-limit → injection-check → history → LLM → reply."""

    # Step 1: Rate limiting
    if not rate_limiter.check(session_id):
        await bot.send(
            event,
            MessageSegment.reply(event.message_id)
            + "You're sending messages too fast. Please wait a moment.",
        )
        return

    # Step 1.5: Prompt-injection detection
    if _detect_injection(message_text):
        logger.warning(
            f"Prompt injection detected from session {session_id}: "
            f"{message_text[:100]}"
        )
        await bot.send(
            event,
            MessageSegment.reply(event.message_id)
            + "Your message contains unsafe instructions and has been blocked.",
        )
        return

    # Step 2: Add user message to history
    session_manager.add_message(session_id, "user", message_text)

    # Step 3: Get conversation context
    messages = session_manager.get_context(session_id)

    # Step 4: Call LLM
    try:
        response = await llm_client.chat(
            messages=messages,
            system_prompt=config.effective_system_prompt,
        )
    except ChatAPIError as e:
        logger.warning(f"LLM API error for session {session_id}: {e}")
        session_manager.reset_session(session_id)
        await bot.send(
            event,
            MessageSegment.reply(event.message_id) + f"{e}",
        )
        return
    except Exception:
        logger.opt(exception=True).error(
            f"Unexpected error for session {session_id}"
        )
        session_manager.reset_session(session_id)
        await bot.send(
            event,
            MessageSegment.reply(event.message_id)
            + "An unexpected error occurred. Please try again later.",
        )
        return

    # Step 5: Add assistant response to history
    session_manager.add_message(session_id, "assistant", response)

    # Step 6: Send response (split long messages)
    await _send_long_message(bot, event, response)


# ------------------------------------------------------------------
# Message helpers
# ------------------------------------------------------------------
async def _send_long_message(
    bot: Bot, event: MessageEvent, text: str
) -> None:
    """Send a message, splitting if it exceeds QQ's length limit."""
    if len(text) <= MAX_MSG_LENGTH:
        await bot.send(event, text)
        return

    # Split into paragraphs, then recombine into chunks under the limit
    chunks: list[str] = []
    current = ""
    for para in text.split("\n"):
        if len(current) + len(para) + 1 > MAX_MSG_LENGTH:
            if current:
                chunks.append(current)
            if len(para) > MAX_MSG_LENGTH:
                while len(para) > MAX_MSG_LENGTH:
                    chunks.append(para[:MAX_MSG_LENGTH])
                    para = para[MAX_MSG_LENGTH:]
                current = para
            else:
                current = para
        else:
            current = (current + "\n" + para) if current else para
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        prefix = f"[{i + 1}/{len(chunks)}] " if len(chunks) > 1 else ""
        await bot.send(event, prefix + chunk)
