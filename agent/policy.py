"""Decision policy for the product search agent."""

from __future__ import annotations

from dataclasses import dataclass

from agent.state import SearchState

SEARCH_WEB = "SEARCH_WEB"
REFINE_QUERY = "REFINE_QUERY"
RERANK_PRODUCTS = "RERANK_PRODUCTS"
STOP = "STOP"


@dataclass
class PolicyDecision:
    action: str
    reason: str


class RetrievalPolicy:
    """Small explicit policy for deciding whether to search, refine, or stop."""

    def __init__(self, result_limit: int = 10, good_score_threshold: float = 0.72) -> None:
        self.result_limit = result_limit
        self.good_score_threshold = good_score_threshold

    def decide_after_search(self, state: SearchState, step: int, max_steps: int) -> PolicyDecision:
        if state.is_equivalent_to_previous():
            return PolicyDecision(STOP, "equivalent_state")

        if self._has_good_results(state):
            return PolicyDecision(STOP, "enough_relevant_products")

        if step < max_steps - 1:
            return PolicyDecision(REFINE_QUERY, "needs_more_relevant_products")

        return PolicyDecision(STOP, "max_steps")

    def _has_good_results(self, state: SearchState) -> bool:
        if len(state.products) < self.result_limit:
            return False
        top_products = state.products[: self.result_limit]
        average_score = sum(product.relevance_score for product in top_products) / self.result_limit
        return average_score >= self.good_score_threshold
