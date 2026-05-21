"""Offline tests for core agent helpers."""

import unittest
from tempfile import TemporaryDirectory

from agent.api_budget import ApiBudget, ApiBudgetExceeded
from agent.memory import MemoryManager
from agent.json_utils import loads_model_json
from agent.prompts import (
    AMBIGUITY_CHECK_PROMPT,
    MEMORY_COMPACTION_PROMPT,
    PRODUCT_SEARCH_PROMPT,
    QUERY_REFINEMENT_PROMPT,
)
from agent.policy import REFINE_QUERY, STOP, RetrievalPolicy
from agent.reranker import ProductReranker
from agent.skill_loader import SkillLoader
from agent.state import SearchState
from schema.ethics import EthicsRating
from schema.locale import SearchLocale
from schema.product import Product
from tools.duckduckgo_search import SearchResult
from tools.brand_resolution import brand_for_product, brand_from_source
from tools.brand_index import find_brand_entry, find_brand_entry_by_name
from tools.ethics_lookup import _normalize_brand
from tools.good_on_you_direct import brand_slug, extract_rating_from_good_on_you_html
from tools.search_result_products import normalize_result_url, product_from_search_result


class CoreHelperTests(unittest.TestCase):
    def test_model_json_parser_accepts_fenced_json(self) -> None:
        data = loads_model_json('```json\n{"refined_query": "trail shoes"}\n```')
        self.assertEqual(data["refined_query"], "trail shoes")

    def test_prompt_templates_format_without_json_brace_errors(self) -> None:
        PRODUCT_SEARCH_PROMPT.format(query="shoes", limit=10, locale_context="Country: Sweden")
        QUERY_REFINEMENT_PROMPT.format(
            agent_context="{}",
            original_query="shoes",
            current_query="trail shoes",
            candidates="[]",
        )
        AMBIGUITY_CHECK_PROMPT.format(
            query="shoes",
            locale_context="Country: Sweden",
            memory_summary="{}",
        )
        MEMORY_COMPACTION_PROMPT.format(
            previous_summary="{}",
            recent_searches="[]",
        )

    def test_product_score_is_clamped(self) -> None:
        product = Product.from_dict(
            {"title": "A", "url": "https://example.com/a", "relevance_score": 2}
        )
        self.assertEqual(product.relevance_score, 1.0)

    def test_reranker_deduplicates_by_url(self) -> None:
        products = [
            Product(title="Old", url="https://example.com/a", relevance_score=0.4),
            Product(title="New", url="https://example.com/a", relevance_score=0.9),
        ]
        reranked = ProductReranker().top_k(products)
        self.assertEqual(len(reranked), 1)
        self.assertEqual(reranked[0].title, "New")

    def test_ethical_mode_boosts_better_rated_brands_without_filtering(self) -> None:
        relevant_but_low_ethics = Product(
            title="Relevant",
            url="https://example.com/relevant",
            relevance_score=0.9,
            ethics=EthicsRating.rated("We avoid"),
        )
        slightly_less_relevant_but_good = Product(
            title="Good",
            url="https://example.com/good",
            relevance_score=0.85,
            ethics=EthicsRating.rated("Good"),
        )

        reranked = ProductReranker().top_k(
            [relevant_but_low_ethics, slightly_less_relevant_but_good],
            ethical_mode=True,
        )

        self.assertEqual(len(reranked), 2)
        self.assertEqual(reranked[0].title, "Good")
        self.assertEqual(reranked[1].title, "Relevant")

    def test_policy_refines_when_results_are_insufficient(self) -> None:
        state = SearchState(original_query="x", current_query="x", products=[])
        decision = RetrievalPolicy(result_limit=10).decide_after_search(
            state, step=0, max_steps=3
        )
        self.assertEqual(decision.action, REFINE_QUERY)

    def test_policy_stops_on_equivalent_state(self) -> None:
        state = SearchState(
            original_query="x",
            current_query="x",
            products=[Product(title="A", url="https://example.com/a", relevance_score=0.5)],
            previous_query="x",
            previous_product_keys=["https://example.com/a"],
        )
        decision = RetrievalPolicy(result_limit=10).decide_after_search(
            state, step=1, max_steps=3
        )
        self.assertEqual(decision.action, STOP)
        self.assertEqual(decision.reason, "equivalent_state")

    def test_memory_round_trips_ethics_cache(self) -> None:
        with TemporaryDirectory() as directory:
            memory = MemoryManager(directory)
            memory.set_ethics_rating("patagonia", EthicsRating.rated("Good"))
            cached = memory.get_ethics_rating("patagonia")
            self.assertIsNotNone(cached)
            self.assertEqual(cached.rating, "Good")

    def test_memory_round_trips_compact_context(self) -> None:
        with TemporaryDirectory() as directory:
            memory = MemoryManager(directory)
            memory.save_compact_context(
                {
                    "summary": "User often searches outdoor products in Sweden.",
                    "retrieval_preferences": ["Prefer Swedish stores."],
                    "avoid": ["Avoid generic category pages."],
                    "last_updated_reason": "Observed repeated searches.",
                }
            )
            compact = memory.load_compact_context()
            self.assertIn("Sweden", compact["summary"])
            self.assertEqual(compact["retrieval_preferences"], ["Prefer Swedish stores."])

    def test_skill_loader_discovers_default_skills(self) -> None:
        loader = SkillLoader()
        names = {skill.name for skill in loader.list_skills()}
        self.assertIn("ethical_shopping", names)
        self.assertIn("taxonomy_search", names)

    def test_search_result_can_be_used_as_product_fallback(self) -> None:
        result = SearchResult(
            title="Waterproof Hiking Shoes",
            url="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fshoe",
            snippet="A waterproof trail shoe for hiking.",
        )
        product = product_from_search_result(result, "waterproof hiking shoes")
        self.assertEqual(product.title, "Waterproof Hiking Shoes")
        self.assertEqual(product.source, "example.com")
        self.assertEqual(product.url, "https://example.com/shoe")
        self.assertGreater(product.relevance_score, 0)

    def test_duckduckgo_redirect_url_is_normalized(self) -> None:
        url = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fshop.example%2Fp%2F1&rut=abc"
        self.assertEqual(normalize_result_url(url), "https://shop.example/p/1")

    def test_locale_boosts_matching_regional_domain(self) -> None:
        result = SearchResult(
            title="Waterproof hiking shoes",
            url="https://example.se/shoes",
            snippet="Available in Sweden for 1500 SEK.",
        )
        localized = product_from_search_result(
            result,
            "waterproof hiking shoes",
            SearchLocale(country="Sweden", market="se-sv", currency="SEK"),
        )
        generic = product_from_search_result(result, "waterproof hiking shoes")
        self.assertGreater(localized.relevance_score, generic.relevance_score)

    def test_api_budget_raises_when_exhausted(self) -> None:
        budget = ApiBudget(max_calls=1)
        budget.consume("first")
        with self.assertRaises(ApiBudgetExceeded):
            budget.consume("second")

    def test_good_on_you_brand_slug(self) -> None:
        self.assertEqual(brand_slug("Helly Hansen"), "helly-hansen")
        self.assertEqual(brand_slug("HOKA"), "hoka")
        self.assertEqual(brand_slug("On"), "on")
        self.assertEqual(brand_slug("Helly Hansen Japan"), "helly-hansen-japan")
        self.assertEqual(brand_slug("Decathlon"), "decathlon")

    def test_good_on_you_rating_parser(self) -> None:
        html = "<h1>Helly Hansen</h1><p>Rated: It's a start</p>"
        self.assertEqual(extract_rating_from_good_on_you_html(html), "It's a start")

    def test_good_on_you_rating_parser_handles_html_entities(self) -> None:
        html = "<h1>On Running</h1><p>Rated: It&#x27;s a start</p>"
        self.assertEqual(extract_rating_from_good_on_you_html(html), "It's a start")

    def test_good_on_you_rating_parser_ignores_similar_brand_ratings(self) -> None:
        html = """
        <main>
          <h1>HOKA</h1>
          <p>Rated: It&#x27;s a start</p>
          <h2>Similar brands</h2>
          <article><h3>Other Brand</h3><p>Rated: Good</p></article>
        </main>
        """
        self.assertEqual(extract_rating_from_good_on_you_html(html), "It's a start")

    def test_brand_resolution_from_query_and_source(self) -> None:
        brand = brand_for_product(
            query="Decathlon waterproof hiking jacket",
            title="Hiking Jackets - Decathlon",
            url="https://www.decathlon.com/collections/hiking-jackets",
            source="decathlon.com",
        )
        self.assertEqual(brand, "Decathlon")

    def test_brand_index_finds_decathlon_from_source(self) -> None:
        entry = find_brand_entry("Hiking Jackets - Decathlon https://www.decathlon.com")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.slug, "decathlon")

    def test_on_brand_is_indexed_for_cache_retry(self) -> None:
        self.assertEqual(_normalize_brand("On"), "on")
        self.assertIsNone(find_brand_entry("On"))
        entry = find_brand_entry_by_name("On")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.slug, "on")

    def test_brand_resolution_uses_source_not_query_prefix(self) -> None:
        brand = brand_for_product(
            query="on waterproof hiking shoes",
            title="Waterproof Hiking Shoes | Free Shipping & Returns | On Sweden",
            url="https://www.on.com/en-se/shop/waterproof-shoes",
            source="on.com",
        )
        self.assertEqual(brand, "On")

    def test_brand_resolution_does_not_use_generic_query_as_brand(self) -> None:
        brand = brand_for_product(
            query="on waterproof hiking shoes",
            title="Waterproof Hiking Shoes",
            url="https://example.com/shoes",
            source="example.com",
        )
        self.assertEqual(brand, "Example")

    def test_brand_resolution_uses_source_prefix(self) -> None:
        self.assertEqual(brand_from_source("stadium.se"), "Stadium")
        self.assertEqual(brand_from_source("adidas.se"), "Adidas")
        self.assertEqual(brand_from_source("championstore.com"), "Champion")



if __name__ == "__main__":
    unittest.main()
