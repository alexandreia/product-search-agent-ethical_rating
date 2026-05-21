"""Live product search tool with OpenAI web_search and Berget-compatible fallback."""

from __future__ import annotations

from openai import NotFoundError

from agent.api_budget import ApiBudget, ApiBudgetExceeded
from agent.json_utils import loads_model_json
from agent.prompts import PRODUCT_EXTRACTION_FROM_SEARCH_RESULTS_PROMPT, PRODUCT_SEARCH_PROMPT
from schema.locale import SearchLocale
from schema.product import Product
from tools.chat_completion import create_chat_text
from tools.duckduckgo_search import DuckDuckGoSearch
from tools.openai_client import make_openai_client
from tools.search_result_products import product_from_search_result


class WebProductSearchTool:
    """Retrieve real products from the web."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        budget: ApiBudget | None = None,
        locale: SearchLocale | None = None,
    ) -> None:
        self.model = model
        self.budget = budget
        self.locale = locale or SearchLocale()
        self.client = make_openai_client()
        self.search_backend = DuckDuckGoSearch()

    def search(self, query: str, limit: int = 10) -> list[Product]:
        prompt = PRODUCT_SEARCH_PROMPT.format(
            query=query,
            limit=limit,
            locale_context=self._locale_context(),
        )
        try:
            if self.budget is not None:
                self.budget.consume("responses_web_search")
            response = self.client.responses.create(
                model=self.model,
                tools=[{"type": "web_search"}],
                input=prompt,
            )
            data = loads_model_json(response.output_text)
        except NotFoundError:
            data = self._search_with_duckduckgo(query, limit)
        except ApiBudgetExceeded:
            data = self._search_with_duckduckgo(query, limit, use_llm=False)
        return [
            product
            for product in (Product.from_dict(item) for item in data.get("products", []))
            if product.url
        ][:limit]

    def _search_with_duckduckgo(self, query: str, limit: int, use_llm: bool = True) -> dict:
        localized_query = " ".join(
            part for part in [query, self.locale.query_hint(), "product buy"] if part
        )
        results = self.search_backend.search(
            localized_query,
            limit=max(limit * 2, 10),
            market=self.locale.market,
        )
        search_results = "\n\n".join(result.to_prompt_text() for result in results)
        if not results:
            return {"products": []}
        if not use_llm:
            return {
                "products": [
                    product_from_search_result(result, query, self.locale).to_dict()
                    for result in results[:limit]
                ]
            }

        prompt = PRODUCT_EXTRACTION_FROM_SEARCH_RESULTS_PROMPT.format(
            query=query,
            limit=limit,
            search_results=search_results,
            locale_context=self._locale_context(),
        )
        try:
            text = create_chat_text(
                self.client,
                self.model,
                prompt,
                budget=self.budget,
                label="extract_products",
            )
        except ApiBudgetExceeded:
            return {
                "products": [
                    product_from_search_result(result, query, self.locale).to_dict()
                    for result in results[:limit]
                ]
            }
        data = loads_model_json(text)
        products = [
            product
            for product in (Product.from_dict(item) for item in data.get("products", []))
            if product.url
        ]
        if products:
            return {"products": [product.to_dict() for product in products[:limit]]}
        return {
            "products": [
                product_from_search_result(result, query, self.locale).to_dict()
                for result in results[:limit]
            ]
        }

    def _locale_context(self) -> str:
        return (
            f"Country: {self.locale.country}; "
            f"market/region: {self.locale.market}; "
            f"preferred currency: {self.locale.currency}"
        )
