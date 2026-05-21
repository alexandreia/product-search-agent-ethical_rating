"""OpenAI client construction with clear configuration errors."""

from __future__ import annotations

import os

from openai import OpenAI


def make_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it before running the agent, "
            "for example: export OPENAI_API_KEY='your_api_key_here'"
        )

    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)

