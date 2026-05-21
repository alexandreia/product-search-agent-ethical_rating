"""Search localization settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchLocale:
    country: str = "United States"
    market: str = "us-en"
    currency: str = "USD"

    def query_hint(self) -> str:
        parts = []
        if self.country:
            parts.append(self.country)
        if self.currency:
            parts.append(self.currency)
        return " ".join(parts)

    def to_prompt_context(self) -> str:
        return f"Country: {self.country or 'unknown'}; market: {self.market or 'unknown'}; currency: {self.currency or 'unknown'}"

    def to_dict(self) -> dict:
        return {
            "country": self.country,
            "market": self.market,
            "currency": self.currency,
        }
