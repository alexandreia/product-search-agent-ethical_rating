"""Context construction for agent prompts."""

from __future__ import annotations

import json
from typing import Any

from agent.state import SearchState


class ContextBuilder:
    """Builds compact prompt context from skills, memory, and state."""

    def build(
        self,
        state: SearchState,
        skills: dict[str, str],
        preferences: dict[str, Any],
        recent_searches: list[dict[str, Any]],
        compact_memory: dict[str, Any] | None = None,
    ) -> str:
        context = {
            "active_skills": list(skills.keys()),
            "skill_instructions": _compact_skills(skills),
            "preferences": preferences,
            "compact_memory": compact_memory or {},
            "recent_searches": recent_searches[-5:],
            "current_state": {
                "original_query": state.original_query,
                "current_query": state.current_query,
                "locale": state.locale.to_dict(),
                "search_queries": state.search_queries[-5:],
                "actions": state.actions[-10:],
                "top_products": [
                    product.to_dict(rank=index)
                    for index, product in enumerate(state.products[:5], start=1)
                ],
            },
        }
        return json.dumps(context, indent=2)


def _compact_skills(skills: dict[str, str]) -> dict[str, str]:
    return {name: text[:2500] for name, text in skills.items()}
