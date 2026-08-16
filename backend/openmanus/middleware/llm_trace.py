from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any

from openmanus.log import logger


def _short(text: Any, n: int = 200) -> str:
    s = str(text).replace("\n", " ").strip()
    return s[:n] + ("…" if len(s) > n else "")

class LLMTraceCallback(BaseCallbackHandler):

    def on_chat_model_end(self, response, *, run_id, parent_run_id, **kwargs: Any) -> None:
        try:
            agent_name = "?"
            inv = kwargs.get("invocation_kwargs") or {}
            tags = inv.get("tags") or []
            for t in tags:
                if isinstance(t, str) and t.startswith("openmanus-"):
                    agent_name = t.replace("openmanus-", "")

            gens = response.generations or []
            if gens and gens[0]:
                gen = gens[0][0]
                msg = getattr(gen, "message", None)
                if msg is None:
                    text = getattr(gen, "text", "")
                    logger.warning("[LLM_TRACE] %s → %s", agent_name, _short(text))
                    return
                content = getattr(msg, "content", "")
                if isinstance(content, list):
                    text = " ".join(
                        p.get("text", "") if isinstance(p, dict) else str(p)
                        for p in content
                    )
                else:
                    text = str(content or "")
                tcs = getattr(msg, "tool_calls", None) or []
                tc_info = []
                for tc in tcs:
                    if isinstance(tc, dict):
                        tc_info.append(f"{tc.get('name','?')}({ _short(tc.get('args',{}), 60) })")
                    else:
                        tc_info.append(f"{getattr(tc,'name','?')}")
                logger.warning(
                    "[LLM_TRACE] %s → text=%r tools=%s",
                    agent_name, _short(text),
                    tc_info if tc_info else "(none)",
                )
        except Exception:
            pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        pass
