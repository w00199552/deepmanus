from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_provider: str = "anthropic"
    model: str = "GLM-5.2"

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://open.bigmodel.cn/api/anthropic"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ssl_verify: bool = True

    workdir: str = str(Path.cwd())

    database_url: str = "sqlite:///./data/checkpoints.db"

    host: str = "127.0.0.1"
    port: int = 8999
    cors_origins: str = "*"

    system_prompt: str = (
        "You are manus, an AI coding agent operating in the user's project "
        "directory. Use the file system tools to read, edit, and run code. "
        "Be concise. Explain what you are about to do, then do it."
    )

    model_retry_enabled: bool = True
    model_retry_max_attempts: int = 3
    model_retry_initial_delay: float = 1.0
    model_retry_backoff_factor: float = 2.0
    model_retry_max_delay: float = 60.0
    model_retry_jitter: bool = True
    model_retry_on_failure: str = "continue"

    tool_retry_enabled: bool = False
    tool_retry_max_attempts: int = 2
    tool_retry_initial_delay: float = 0.5
    tool_retry_backoff_factor: float = 2.0
    tool_retry_max_delay: float = 30.0
    tool_retry_jitter: bool = True
    tool_retry_on_failure: str = "continue"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()
