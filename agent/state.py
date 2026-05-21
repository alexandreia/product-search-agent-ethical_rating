"""Working memory for the product search agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from schema.product import Product
from schema.locale import SearchLocale


@dataclass
class SearchState:
    """State tracked across search/refine/rerank/stop iterations."""

    original_query: str
    current_query: str
    locale: SearchLocale = field(default_factory=SearchLocale)
    products: list[Product] = field(default_factory=list)
    previous_query: str | None = None
    previous_product_keys: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    stop_reason: str | None = None

    def product_keys(self) -> list[str]:
        return [product.dedupe_key() for product in self.products]

    def is_equivalent_to_previous(self) -> bool:
        return (
            self.previous_query == self.current_query
            and self.previous_product_keys == self.product_keys()
        )

    def remember_previous(self) -> None:
        self.previous_query = self.current_query
        self.previous_product_keys = self.product_keys()
