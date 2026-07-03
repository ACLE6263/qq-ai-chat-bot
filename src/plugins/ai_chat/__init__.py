"""AI Chat Plugin — LLM-powered conversation for QQ."""

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="AI Chat",
    description="基于 Claude/OpenAI API 的 QQ 智能对话插件",
    usage=(
        "私聊：直接发送消息即可对话\n"
        "群聊：@机器人 + 消息内容\n"
        "/reset 或 /clear — 清除当前对话历史"
    ),
    supported_adapters={"~onebot.v11"},
    extra={
        "author": "QQ Bot",
        "version": "1.0.0",
    },
)

# Import handlers to register matchers
from .chat_handler import (  # noqa: E402, F401
    group_chat,
    handle_group,
    handle_private,
    handle_reset,
    private_chat,
    reset_cmd,
)
