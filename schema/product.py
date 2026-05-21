"""Product result schema used by the product search agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schema.ethics import EthicsRating


@dataclass
class Product:
    """A normalized product candidate returned from live product search."""

    title: str
    url: str
    source: str = ""
    brand: str | None = None
    price: str | None = None
    currency: str | None = None
    category_path: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    reason: str = ""
    ethics: EthicsRating | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        score = _clamp_score(data.get("relevance_score"))
        return cls(
            title=str(data.get("title") or "Untitled product"),
            url=str(data.get("url") or ""),
            source=str(data.get("source") or ""),
            brand=data.get("brand"),
            price=data.get("price"),
            currency=data.get("currency"),
            category_path=data.get("category_path"),
            attributes=data.get("attributes") or {},
            relevance_score=score,
            reason=str(data.get("reason") or ""),
            ethics=data.get("ethics"),
        )

    def dedupe_key(self) -> str:
        return self.url.rstrip("/").lower() or self.title.lower()

    def to_dict(self, rank: int | None = None) -> dict[str, Any]:
        result = {
            "title": self.title,
            "brand": self.brand,
            "price": self.price,
            "currency": self.currency,
            "category_path": self.category_path,
            "attributes": self.attributes,
            "source": self.source,
            "url": self.url,
            "relevance_score": round(self.relevance_score, 3),
            "reason": self.reason,
        }
        if self.ethics is not None:
            result["ethics"] = self.ethics.to_dict()
        if rank is not None:
            result = {"rank": rank, **result}
        return result


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, score))
