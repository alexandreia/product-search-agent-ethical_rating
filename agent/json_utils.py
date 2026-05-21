"""JSON parsing helpers for model outputs."""

from __future__ import annotations

import json
import re
from typing import Any


def loads_model_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from an LLM response.

    Models usually follow the "JSON only" instruction, but this helper also
    tolerates fenced blocks or short surrounding text so demos do not fail on a
    cosmetic formatting slip.
    """
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)

    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse model JSON output: {text[:500]}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Expected model output to be a JSON object.")
    return parsed

