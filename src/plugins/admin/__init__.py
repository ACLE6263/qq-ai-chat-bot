"""Admin Plugin — management commands for the bot owner."""

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Admin",
    description="管理员命令插件，仅 bot 主人可用",
    usage=(
        "/status — 查看机器人运行状态\n"
        "/ping   — 检查机器人是否在线"
    ),
    supported_adapters={"~onebot.v11"},
    extra={
        "author": "QQ Bot",
        "version": "1.0.0",
    },
)

from .commands import ping, show_status, ping_cmd, status_cmd  # noqa: E402, F401
