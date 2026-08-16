from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessageChunk
from langchain_openai import ChatOpenAI

class ChatGLM(ChatOpenAI):

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ):
        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if gen_chunk is None:
            return None
        msg = gen_chunk.message
        if not isinstance(msg, AIMessageChunk):
            return gen_chunk

        choices = (
            chunk.get("choices", [])
            or chunk.get("chunk", {}).get("choices", [])
        )
        if not choices:
            return gen_chunk
        delta = choices[0].get("delta") or {}
        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
        if reasoning:
            existing = msg.additional_kwargs.get("reasoning_content", "")
            msg.additional_kwargs["reasoning_content"] = existing + reasoning
        return gen_chunk
