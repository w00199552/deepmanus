"""Retry middleware builder — exponential backoff for transient LLM/tool errors.

Wraps langchain's built-in ``ModelRetryMiddleware`` / ``ToolRetryMiddleware``
(``langchain.agents.middleware``, available since langchain 1.x) with our
settings-driven configuration, so a single env block controls retry behaviour
for every agent built by ``agent_factory.build_agent``.

Why this module exists (instead of inlining the middlewares in ``build_agent``):
  * The two provider libraries (``openai`` / ``anthropic``) raise DIFFERENT
    exception types, and the active one depends on ``MODEL_PROVIDER``. A single
    ``is_transient(exc)`` callable inspects ``status_code`` uniformly rather than
    enumerating provider-specific exception tuples.
  * Centralising the "what counts as retryable" policy in one place keeps
    ``agent_factory`` focused on agent assembly.

Retryable = transient errors only:
  * 429 RateLimitError (company/self-hosted model throttling — the original
    motivation for this module)
  * APITimeoutError / APIConnectionError / httpx transport errors (network jitter)
  * 5xx InternalServerError / OverloadedError (server-side, may recover)

NOT retryable (retrying won't help):
  * 4xx client errors: 401/403 auth, 400 bad request, 404 not found, …
  * Anything else (ValueError, programming bugs, …) — surface immediately.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.middleware.types import AgentMiddleware

logger = logging.getLogger(__name__)

# --- provider exception classes (optional imports; only the active provider
#     need be installed, so guard each import) ------------------------------
_OAI_EXC: dict[str, type] = {}
try:
    from openai import (
        APIConnectionError as _OAIConn,
        APIStatusError as _OAIStatus,
        APITimeoutError as _OAITimeout,
    )
    _OAI_EXC = {"conn": _OAIConn, "status": _OAIStatus, "timeout": _OAITimeout}
except Exception:  # noqa: BLE001 — openai not installed in this env
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
except Exception:  # noqa: BLE001 — anthropic not installed in this env
    pass

# httpx is a hard dependency (used by _build_model), so this import is safe.
import httpx  # noqa: E402


# Network-layer exceptions from httpx/httpcore that indicate a transient
# transport failure worth retrying. ReadTimeout covers slow model responses.
_HTTPX_TRANSIENT = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
)
try:  # httpcore raises some errors langchain re-raises directly
    import httpcore
    _HTTPX_TRANSIENT = (*_HTTPX_TRANSIENT, httpcore.RemoteProtocolError)
except Exception:  # noqa: BLE001
    pass


def is_transient(exc: Exception) -> bool:
    """Return ``True`` if ``exc`` is a transient error worth retrying.

    Policy:
      * Provider RateLimit/Timeout/Connection/5xx → retry (may recover)
      * Provider 4xx (auth/bad-request/not-found) → don't retry (won't change)
      * httpx transport errors → retry
      * everything else → don't retry (likely a bug, not a blip)
    """
    if exc is None:
        return False

    # 1. anthropic provider exceptions (OverloadedError is anthropic's 529).
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

    # 2. openai provider exceptions.
    if _OAI_EXC:
        if isinstance(exc, _OAI_EXC.get("timeout", ())):
            return True
        if isinstance(exc, _OAI_EXC.get("conn", ())):
            return True
        oai_status = _OAI_EXC.get("status")
        if oai_status and isinstance(exc, oai_status):
            code = getattr(exc, "status_code", None)
            # 429 (RateLimitError subclasses APIStatusError with code=429),
            # 5xx → retry. 4xx (auth/bad-request) → don't.
            return code is not None and (code == 429 or code >= 500)

    # 3. httpx / httpcore transport errors.
    if _HTTPX_TRANSIENT and isinstance(exc, _HTTPX_TRANSIENT):
        return True

    return False


def build_retry_middlewares(settings: Any) -> list[AgentMiddleware]:
    """Build the retry middlewares requested by ``settings``.

    Returns a (possibly empty) list, ordered so retry wraps OUTSIDE guard/trace
    (caller prepends it). Empty list when both retries are disabled or
    ``max_attempts`` is too low to allow any retry.

    Args:
        settings: the :class:`openmanus.config.Settings` instance (duck-typed —
            only the ``*_retry_*`` attributes are read).
    """
    middlewares: list[AgentMiddleware] = []

    # --- model-call retry -------------------------------------------------
    if settings.model_retry_enabled:
        # max_attempts counts the FIRST try; middleware's max_retries excludes
        # it. Guard against max_attempts=1 (one try, zero retries → still builds
        # the middleware, which then just never retries, useful for jitter-free
        # on_failure routing) and max_attempts<=0 (skip entirely).
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

    # --- tool-call retry --------------------------------------------------
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
