"""Admin commands — accessible only by the bot owner."""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from src.config import config
from src.plugins.ai_chat.session_manager import session_manager

# ------------------------------------------------------------------
# Matchers (SUPERUSER = bot owner QQ configured in .env)
# ------------------------------------------------------------------
status_cmd = on_command(
    "status",
    priority=1,
    block=True,
    permission=SUPERUSER,
)

ping_cmd = on_command(
    "ping",
    priority=1,
    block=True,
    permission=SUPERUSER,
)

# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------
@status_cmd.handle()
async def show_status(bot: Bot, event: MessageEvent) -> None:
    """Show bot runtime status."""
    provider = config.llm_provider
    model = (
        config.claude_model
        if provider == "claude"
        else config.openai_model
        if provider == "openai"
        else config.custom_model
    )

    msg = (
        "🤖 Bot Status\n"
        f"Provider: {provider}\n"
        f"Model: {model}\n"
        f"Active Sessions: {session_manager.get_total_active_sessions()}\n"
        f"Trigger Mode: {config.trigger_mode}\n"
        f"Max History Turns: {config.max_history_turns}\n"
        f"Max Response Tokens: {config.max_response_tokens}\n"
    )
    await status_cmd.finish(MessageSegment.reply(event.message_id) + msg)


@ping_cmd.handle()
async def ping(bot: Bot, event: MessageEvent) -> None:
    """Simple liveness check."""
    await ping_cmd.finish(
        MessageSegment.reply(event.message_id) + "pong!"
    )
