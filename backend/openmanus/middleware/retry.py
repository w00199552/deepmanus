from __future__ import annotations

from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware
from typing import Any

from openmanus.log import logger

_OAI_EXC: dict[str, type] = {}
try:
    from openai import (
        APIConnectionError as _OAIConn,
        APIStatusError as _OAIStatus,
        APITimeoutError as _OAITimeout,
    )
    _OAI_EXC = {"conn": _OAIConn, "status": _OAIStatus, "timeout": _OAITimeout}
except Exception:
    pass

_ANT_EXC: dict[str, type] = {}
try:
    from anthropic import (
        APIConnectionError as _ANTConn,
        APIStatusError as _ANTStatus,
        APITimeoutError as _ANTTimeout,
        OverloadedError as _ANTOverloaded,
    )
    _ANT_EXC = {
        "conn": _ANTConn, "status": _ANTStatus,
        "timeout": _ANTTimeout, "overloaded": _ANTOverloaded,
    }
except Exception:
    pass

import httpx

_HTTPX_TRANSIENT = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
)
try:
    import httpcore
    _HTTPX_TRANSIENT = (*_HTTPX_TRANSIENT, httpcore.RemoteProtocolError)
except Exception:
    pass

def is_transient(exc: Exception) -> bool:
    if exc is None:
        return False

    if _ANT_EXC:
        if isinstance(exc, _ANT_EXC.get("overloaded", ())):
            return True
        if isinstance(exc, _ANT_EXC.get("timeout", ())):
            return True
        if isinstance(exc, _ANT_EXC.get("conn", ())):
            return True
        ant_status = _ANT_EXC.get("status")
        if ant_status and isinstance(exc, ant_status):
            code = getattr(exc, "status_code", None)
            return code is not None and code >= 500

    if _OAI_EXC:
        if isinstance(exc, _OAI_EXC.get("timeout", ())):
            return True
        if isinstance(exc, _OAI_EXC.get("conn", ())):
            return True
        oai_status = _OAI_EXC.get("status")
        if oai_status and isinstance(exc, oai_status):
            code = getattr(exc, "status_code", None)
            return code is not None and (code == 429 or code >= 500)

    if _HTTPX_TRANSIENT and isinstance(exc, _HTTPX_TRANSIENT):
        return True

    return False

def build_retry_middlewares(settings: Any) -> list[AgentMiddleware]:
    middlewares: list[AgentMiddleware] = []

    if settings.model_retry_enabled:
        retries = max(0, settings.model_retry_max_attempts - 1)
        middlewares.append(ModelRetryMiddleware(
            max_retries=retries,
            retry_on=is_transient,
            backoff_factor=settings.model_retry_backoff_factor,
            initial_delay=settings.model_retry_initial_delay,
            max_delay=settings.model_retry_max_delay,
            jitter=settings.model_retry_jitter,
            on_failure=settings.model_retry_on_failure,
        ))
        logger.info(
            "ModelRetryMiddleware enabled: max_attempts=%d (retries=%d) "
            "initial=%.1fs backoff=%.1f cap=%.1fs jitter=%s on_failure=%s",
            settings.model_retry_max_attempts, retries,
            settings.model_retry_initial_delay,
            settings.model_retry_backoff_factor,
            settings.model_retry_max_delay,
            settings.model_retry_jitter,
            settings.model_retry_on_failure,
        )

    if settings.tool_retry_enabled:
        retries = max(0, settings.tool_retry_max_attempts - 1)
        middlewares.append(ToolRetryMiddleware(
            max_retries=retries,
            retry_on=is_transient,
            backoff_factor=settings.tool_retry_backoff_factor,
            initial_delay=settings.tool_retry_initial_delay,
            max_delay=settings.tool_retry_max_delay,
            jitter=settings.tool_retry_jitter,
            on_failure=settings.tool_retry_on_failure,
        ))
        logger.info(
            "ToolRetryMiddleware enabled: max_attempts=%d (retries=%d) "
            "initial=%.1fs backoff=%.1f cap=%.1fs jitter=%s on_failure=%s",
            settings.tool_retry_max_attempts, retries,
            settings.tool_retry_initial_delay,
            settings.tool_retry_backoff_factor,
            settings.tool_retry_max_delay,
            settings.tool_retry_jitter,
            settings.tool_retry_on_failure,
        )

    return middlewares
