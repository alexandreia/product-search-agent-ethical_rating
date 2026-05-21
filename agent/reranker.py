"""Reranking helpers for product candidates."""

from __future__ import annotations

from schema.product import Product


class ProductReranker:
    """Deterministic reranker using relevance plus optional ethics boost."""

    def top_k(
        self,
        products: list[Product],
        k: int = 10,
        ethical_mode: bool = False,
        ethics_weight: float = 0.2,
    ) -> list[Product]:
        deduped: dict[str, Product] = {}
        for product in products:
            key = product.dedupe_key()
            current = deduped.get(key)
            if current is None or _combined_score(product, ethical_mode, ethics_weight) > _combined_score(
                current, ethical_mode, ethics_weight
            ):
                deduped[key] = product

        return sorted(
            deduped.values(),
            key=lambda product: (
                _combined_score(product, ethical_mode, ethics_weight),
                product.relevance_score,
                bool(product.price),
                product.title,
            ),
            reverse=True,
        )[:k]


def _combined_score(product: Product, ethical_mode: bool, ethics_weight: float) -> float:
    if not ethical_mode or product.ethics is None or product.ethics.status != "rated":
        return product.relevance_score
    relevance_weight = 1.0 - ethics_weight
    return relevance_weight * product.relevance_score + ethics_weight * product.ethics.score
