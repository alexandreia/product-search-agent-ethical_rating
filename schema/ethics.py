"""Ethical brand rating schema."""

from __future__ import annotations

from dataclasses import dataclass


GOOD_ON_YOU_SOURCE = "Good On You"
GOOD_ON_YOU_URL = "https://directory.goodonyou.eco/"


RATING_SCORES = {
    "great": 1.0,
    "good": 0.8,
    "it's a start": 0.55,
    "not good enough": 0.25,
    "we avoid": 0.0,
}


@dataclass
class EthicsRating:
    """Brand-level rating from Good On You."""

    source: str = GOOD_ON_YOU_SOURCE
    status: str = "not_rated"
    rating: str | None = None
    score: float = 0.0
    source_url: str = GOOD_ON_YOU_URL
    note: str = "Brand was not found in the Good On You directory."

    @classmethod
    def rated(cls, rating: str, source_url: str = GOOD_ON_YOU_URL) -> "EthicsRating":
        normalized = rating.strip().lower()
        return cls(
            status="rated",
            rating=rating,
            score=RATING_SCORES.get(normalized, 0.0),
            source_url=source_url,
            note=f"Good On You rates this brand as {rating}.",
        )

    @classmethod
    def not_rated(cls, brand: str | None) -> "EthicsRating":
        label = brand or "Brand"
        return cls(note=f"{label} was not found in the Good On You directory.")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "status": self.status,
            "rating": self.rating,
            "score": round(self.score, 3),
            "source_url": self.source_url,
            "note": self.note,
        }

