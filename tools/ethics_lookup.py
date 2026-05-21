"""Good On You brand rating lookup tool.

This is intentionally deterministic: it normalizes a brand name into a Good On
You slug, retrieves that exact brand page, parses the rating if present, and
caches the result. It does not infer ratings with an LLM.
"""

from __future__ import annotations

from agent.memory import MemoryManager
from schema.ethics import EthicsRating
from tools.brand_index import find_brand_entry_by_name
from tools.good_on_you_direct import direct_good_on_you_lookup


class GoodOnYouLookup:
    """Looks up brand ratings from Good On You using deterministic retrieval."""

    def __init__(self, memory: MemoryManager | None = None) -> None:
        self.memory = memory
        self._cache: dict[str, EthicsRating] = {}

    def lookup(
        self,
        brand: str | None,
        *,
        product_title: str = "",
        product_url: str = "",
        product_source: str = "",
    ) -> EthicsRating:
        if not brand:
            return EthicsRating.not_rated(brand)

        key = _normalize_brand(brand)
        if key in self._cache:
            return self._cache[key]
        if self.memory is not None:
            cached = self.memory.get_ethics_rating(key)
            if cached is not None:
                if cached.status == "rated" or find_brand_entry_by_name(brand) is None:
                    self._cache[key] = cached
                    return cached

        rating = direct_good_on_you_lookup(brand)
        self._cache[key] = rating
        if self.memory is not None:
            self.memory.set_ethics_rating(key, rating)
        return rating


def _normalize_brand(brand: str) -> str:
    return " ".join(brand.lower().strip().split())
