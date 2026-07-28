"""Retry middleware — transient-error detection + builder.

Covers:
  * ``is_transient`` decision matrix across provider exception types and
    httpx transport errors (the core policy: 429/5xx/timeout → retry,
    4xx/bugs → don't).
  * ``build_retry_middlewares`` — default config (ModelRetry on, ToolRetry off),
    both-off (empty list), and the ``max_attempts`` → ``max_retries`` conversion.

Tests construct REAL provider exceptions (openai is a hard dep via
langchain-openai) so the policy is exercised against actual class hierarchies,
not mocks. anthropic is optional, so those branches are skipped when absent.

Run:  uv run pytest tests/test_retry_config.py -v
"""

from __future__ import annotations

import httpx
import pytest
from langchain.agents.middleware import ModelRetryMiddleware, ToolRetryMiddleware

from openmanus.middleware.retry import build_retry_middlewares, is_transient


# ─── fixtures: real exceptions --------------------------------------------

@pytest.fixture
def http_request():
    return httpx.Request("POST", "https://example.invalid/chat")


@pytest.fixture
def make_oai_exc(http_request):
    """Build a real openai.APIStatusError subclass with a given status code."""
    from openai import APIStatusError

    def _make(exc_cls, status_code):
        resp = httpx.Response(status_code=status_code, request=http_request)
        return exc_cls("boom", response=resp, body=None)

    return _make


# ─── is_transient: openai provider matrix ---------------------------------

def test_is_transient_openai_429_rate_limit(make_oai_exc):
    from openai import RateLimitError
    assert is_transient(make_oai_exc(RateLimitError, 429)) is True


def test_is_transient_openai_500_internal_server(make_oai_exc):
    from openai import InternalServerError
    assert is_transient(make_oai_exc(InternalServerError, 500)) is True


def test_is_transient_openai_502_bad_gateway(make_oai_exc):
    from openai import APIStatusError
    assert is_transient(make_oai_exc(APIStatusError, 502)) is True


def test_is_transient_openai_400_bad_request(make_oai_exc):
    from openai import BadRequestError
    assert is_transient(make_oai_exc(BadRequestError, 400)) is False


def test_is_transient_openai_401_unauthorized(make_oai_exc):
    # 401 auth — retrying won't help, must NOT retry.
    from openai import APIStatusError
    assert is_transient(make_oai_exc(APIStatusError, 401)) is False


def test_is_transient_openai_404_not_found(make_oai_exc):
    from openai import NotFoundError
    assert is_transient(make_oai_exc(NotFoundError, 404)) is False


def test_is_transient_openai_api_timeout(http_request):
    from openai import APITimeoutError
    assert is_transient(APITimeoutError(request=http_request)) is True


def test_is_transient_openai_api_connection_error(http_request):
    from openai import APIConnectionError
    assert is_transient(APIConnectionError(request=http_request)) is True


# ─── is_transient: anthropic provider (skip if not installed) -------------

def test_is_transient_anthropic_overloaded():
    pytest.importorskip("anthropic")
    from anthropic import OverloadedError
    # OverloadedError is anthropic's 529 — server overloaded, retryable.
    # It subclasses APIStatusError, which requires response + body.
    resp = httpx.Response(status_code=529, request=httpx.Request("POST", "https://x"))
    exc = OverloadedError(message="overloaded", response=resp, body=None)
    assert is_transient(exc) is True


def test_is_transient_anthropic_5xx_status():
    anthropic = pytest.importorskip("anthropic")
    from anthropic import APIStatusError
    resp = httpx.Response(status_code=500, request=httpx.Request("POST", "https://x"))
    exc = APIStatusError(message="boom", response=resp, body=None)
    assert is_transient(exc) is True


def test_is_transient_anthropic_4xx_status():
    pytest.importorskip("anthropic")
    from anthropic import APIStatusError
    resp = httpx.Response(status_code=401, request=httpx.Request("POST", "https://x"))
    exc = APIStatusError(message="auth", response=resp, body=None)
    assert is_transient(exc) is False


# ─── is_transient: httpx transport errors + non-retryable -----------------

def test_is_transient_httpx_read_timeout():
    assert is_transient(httpx.ReadTimeout("slow")) is True


def test_is_transient_httpx_connect_error():
    assert is_transient(httpx.ConnectError("no route")) is True


def test_is_transient_httpx_remote_protocol_error():
    assert is_transient(httpx.RemoteProtocolError("dropped")) is True


def test_is_transient_value_error_not_retryable():
    # Programming bugs / non-network errors must surface immediately.
    assert is_transient(ValueError("bug")) is False


def test_is_transient_key_error_not_retryable():
    assert is_transient(KeyError("missing")) is False


def test_is_transient_none_safe():
    assert is_transient(None) is False  # type: ignore[arg-type]


# ─── build_retry_middlewares: configuration matrix ------------------------

class _FakeSettings:
    """Minimal duck-typed stand-in for openmanus.config.Settings.

    Only the ``*_retry_*`` attributes are read by build_retry_middlewares;
    using a fake avoids importing the real Settings (which loads .env).
    """

    def __init__(self, **kw):
        # Defaults mirror config.py so the "default" case is realistic.
        self.model_retry_enabled = True
        self.model_retry_max_attempts = 3
        self.model_retry_initial_delay = 1.0
        self.model_retry_backoff_factor = 2.0
        self.model_retry_max_delay = 60.0
        self.model_retry_jitter = True
        self.model_retry_on_failure = "continue"
        self.tool_retry_enabled = False
        self.tool_retry_max_attempts = 2
        self.tool_retry_initial_delay = 0.5
        self.tool_retry_backoff_factor = 2.0
        self.tool_retry_max_delay = 30.0
        self.tool_retry_jitter = True
        self.tool_retry_on_failure = "continue"
        for k, v in kw.items():
            setattr(self, k, v)


def test_build_defaults_model_only():
    """Default config: ModelRetry on, ToolRetry off → exactly one middleware."""
    mw = build_retry_middlewares(_FakeSettings())
    assert len(mw) == 1
    assert isinstance(mw[0], ModelRetryMiddleware)


def test_build_both_disabled_returns_empty():
    s = _FakeSettings(model_retry_enabled=False, tool_retry_enabled=False)
    assert build_retry_middlewares(s) == []


def test_build_both_enabled_returns_two():
    s = _FakeSettings(model_retry_enabled=True, tool_retry_enabled=True)
    mw = build_retry_middlewares(s)
    assert len(mw) == 2
    assert isinstance(mw[0], ModelRetryMiddleware)
    assert isinstance(mw[1], ToolRetryMiddleware)


def test_build_max_attempts_to_retries_conversion():
    """max_attempts counts the first try; middleware's max_retries excludes it.

    max_attempts=3 → max_retries=2. max_attempts=1 → max_retries=0 (build the
    middleware anyway; it just never retries, useful for on_failure routing).
    """
    s = _FakeSettings(model_retry_max_attempts=3)
    mw = build_retry_middlewares(s)
    assert mw[0].max_retries == 2

    s1 = _FakeSettings(model_retry_max_attempts=1)
    assert build_retry_middlewares(s1)[0].max_retries == 0


def test_build_max_attempts_zero_no_negative_retries():
    """Defensive: max_attempts<=0 must not produce negative max_retries."""
    s = _FakeSettings(model_retry_max_attempts=0)
    mw = build_retry_middlewares(s)
    # Still built (enabled=True), but retries clamped to 0.
    assert mw[0].max_retries == 0


def test_build_forwards_all_params():
    s = _FakeSettings(
        model_retry_enabled=True,
        model_retry_max_attempts=5,
        model_retry_initial_delay=2.0,
        model_retry_backoff_factor=1.5,
        model_retry_max_delay=30.0,
        model_retry_jitter=False,
        model_retry_on_failure="error",
    )
    mw = build_retry_middlewares(s)
    m = mw[0]
    assert m.max_retries == 4
    assert m.initial_delay == 2.0
    assert m.backoff_factor == 1.5
    assert m.max_delay == 30.0
    assert m.jitter is False
    assert m.on_failure == "error"


def test_build_tool_retry_forwards_params():
    s = _FakeSettings(
        model_retry_enabled=False,
        tool_retry_enabled=True,
        tool_retry_max_attempts=4,
        tool_retry_initial_delay=0.25,
        tool_retry_backoff_factor=3.0,
    )
    mw = build_retry_middlewares(s)
    assert len(mw) == 1
    t = mw[0]
    assert isinstance(t, ToolRetryMiddleware)
    assert t.max_retries == 3
    assert t.initial_delay == 0.25
    assert t.backoff_factor == 3.0


def test_build_middlewares_use_is_transient():
    """The retry_on policy must be our is_transient callable, not a tuple."""
    from openmanus.middleware.retry import is_transient as policy
    s = _FakeSettings(model_retry_enabled=True, tool_retry_enabled=True)
    mw = build_retry_middlewares(s)
    assert mw[0].retry_on is policy
    assert mw[1].retry_on is policy
