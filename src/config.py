"""Pydantic settings model — loads configuration from .env file."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Central configuration for the QQ AI Chat Bot.

    All values are loaded from .env file (or environment variables).

    If ``system_prompt.txt`` exists next to ``.env``, its content is used
    as the system prompt regardless of the SYSTEM_PROMPT env-var value.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # NoneBot2
    environment: str = "prod"
    driver: str = "~fastapi"
    host: str = "127.0.0.1"
    port: int = 8080

    # OneBot v11
    onebot_access_token: str = ""

    # LLM Provider selection
    llm_provider: Literal["claude", "openai", "custom"] = "claude"

    # Anthropic / Claude
    claude_api_key: str = ""
    claude_api_base: str = "https://api.anthropic.com"
    claude_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # Custom OpenAI-compatible endpoint
    custom_api_base: str = ""
    custom_api_key: str = ""
    custom_model: str = ""
    custom_backup_models: str = ""  # comma-separated fallback model list

    # Chat behavior
    system_prompt: str = ""

    @property
    def effective_system_prompt(self) -> str:
        """Resolve the system prompt — prefer system_prompt.txt, then .env value."""
        prompt_file = Path("system_prompt.txt")
        if prompt_file.is_file():
            return prompt_file.read_text("utf-8").strip()
        if self.system_prompt:
            return self.system_prompt
        return "你是一个运行在 QQ 上的 AI 助手，请用简洁友好的方式回复。"

    max_history_turns: int = 20
    max_response_tokens: int = 1024
    temperature: float = 0.7
    trigger_mode: Literal["at_only", "prefix"] = "at_only"
    chat_prefix: str = "/chat"

    # Rate limiting
    rate_limit_per_user: int = 20
    rate_limit_per_group: int = 60
    rate_limit_window: int = 60

    # Network
    http_proxy: str = ""

    # Admin
    bot_owner_qq: str = ""


# Singleton — import from other modules
config = Config()
