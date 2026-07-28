"""Application configuration loaded from environment / .env.

Two provider modes are supported via the MODEL_PROVIDER setting:

* ``anthropic`` (default for GLM) — uses an Anthropic-protocol-compatible
  endpoint. BigModel's GLM-5.2 exposes
  ``https://open.bigmodel.cn/api/anthropic`` and a standard API key.
* ``openai`` — any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, …).

The agent operates on the real local project files under WORKDIR.
"""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider / model ------------------------------------------------
    # "anthropic" or "openai". GLM-5.2 via BigModel is Anthropic-protocol.
    model_provider: str = "anthropic"
    model: str = "GLM-5.2"

    # Anthropic-protocol credentials (BigModel GLM, Anthropic itself, Z.ai, …)
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://open.bigmodel.cn/api/anthropic"

    # OpenAI-protocol credentials (kept for OpenAI/OpenRouter/Ollama use)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    # Skip TLS certificate verification (set False for self-signed / 公司内网
    # 自建模型证书). Affects BOTH providers' httpx clients.
    ssl_verify: bool = True

    # --- Filesystem the agent works on -----------------------------------
    # Defaults to the current working directory so the agent edits real files.
    workdir: str = str(Path.cwd())

    # --- History persistence (checkpointer) ------------------------------
    # sqlite:///./data/checkpoints.db  or  postgresql+psycopg://user:pass@host/db
    database_url: str = "sqlite:///./data/checkpoints.db"

    # --- Server ----------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8999
    cors_origins: str = "*"

    # --- Agent behaviour -------------------------------------------------
    system_prompt: str = (
        "You are manus, an AI coding agent operating in the user's project "
        "directory. Use the file system tools to read, edit, and run code. "
        "Be concise. Explain what you are about to do, then do it."
    )

    # --- Model-call retry (LLM API 429/超时/5xx) -------------------------
    # 公司内网/自托管模型经常限流(429)或网络抖动,这里用 langchain 的
    # ModelRetryMiddleware 做指数退避重试,透明兜住瞬时错误。
    # 仅对瞬时错误重试(429 RateLimit / 超时 / 连接错误 / 5xx / httpx 网络错误),
    # 4xx 客户端错误(401/400…)不重试 —— 重试无用且浪费时间。
    model_retry_enabled: bool = True
    # 总尝试次数(含首次)。中间件层 max_retries = max_attempts - 1。
    model_retry_max_attempts: int = 3
    # 首次重试前等待秒数(initial_delay)。
    model_retry_initial_delay: float = 1.0
    # 指数退避乘数: 第 n 次重试等待 initial_delay * backoff_factor ** n。
    # 设 0.0 = 固定间隔(不指数增长)。
    model_retry_backoff_factor: float = 2.0
    # 单次等待上限(秒),封顶指数退避增长。
    model_retry_max_delay: float = 60.0
    # ±25% 随机抖动,避免多个并发请求同步重试导致惊群。
    model_retry_jitter: bool = True
    # 所有重试用尽后:
    #   continue = 降级返回错误 AIMessage,agent 继续(默认)
    #   error    = 向上抛出,中断 agent 执行
    model_retry_on_failure: str = "continue"

    # --- Tool-call retry (文件/shell 为确定性操作, 默认关闭) -------------
    # 文件读写/shell 命令多为确定性操作,重试通常无意义(再次执行结果相同),
    # 故默认关闭。若挂了不稳定的远程工具(MCP/网络),可按需开启。
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
