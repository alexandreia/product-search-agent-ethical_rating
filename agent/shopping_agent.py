"""Taxonomy-aware product search agent."""

from __future__ import annotations

import json

from agent.api_budget import ApiBudget, ApiBudgetExceeded
from agent.context import ContextBuilder
from agent.heartbeat import HeartbeatWriter
from agent.json_utils import loads_model_json
from agent.memory import MemoryManager
from agent.policy import REFINE_QUERY, RERANK_PRODUCTS, SEARCH_WEB, STOP, RetrievalPolicy
from agent.prompts import AMBIGUITY_CHECK_PROMPT, MEMORY_COMPACTION_PROMPT, QUERY_REFINEMENT_PROMPT
from agent.reranker import ProductReranker
from agent.skill_loader import SkillLoader
from agent.state import SearchState
from schema.locale import SearchLocale
from tools.chat_completion import create_chat_text
from tools.brand_resolution import brand_for_product
from tools.ethics_lookup import GoodOnYouLookup
from tools.web_product_search import WebProductSearchTool
from tools.openai_client import make_openai_client


class ShoppingSearchAgent:
    """Agent that searches, refines, reranks, and stops over live product data."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        max_steps: int = 3,
        result_limit: int = 10,
        ethical_mode: bool = False,
        skills_dir: str | None = None,
        max_api_calls: int | None = None,
        country: str = "United States",
        market: str = "us-en",
        currency: str = "USD",
        clarify_ambiguous: bool = True,
        compact_memory: bool = True,
    ) -> None:
        self.model = model
        self.max_steps = max_steps
        self.result_limit = result_limit
        self.ethical_mode = ethical_mode
        self.clarify_ambiguous = clarify_ambiguous
        self.compact_memory_enabled = compact_memory
        self.locale = SearchLocale(country=country, market=market, currency=currency)
        self.api_budget = ApiBudget(max_calls=max_api_calls)
        self.memory = MemoryManager()
        self.heartbeat = HeartbeatWriter()
        self.skill_loader = SkillLoader(skills_dir=skills_dir)
        self.context_builder = ContextBuilder()
        self.search_tool = WebProductSearchTool(
            model=model,
            budget=self.api_budget,
            locale=self.locale,
        )
        self.ethics_lookup = GoodOnYouLookup(memory=self.memory) if ethical_mode else None
        self.reranker = ProductReranker()
        self.policy = RetrievalPolicy(result_limit=result_limit)
        self.client = make_openai_client()

    def run(self, query: str) -> dict:
        state = SearchState(original_query=query, current_query=query, locale=self.locale)
        active_skills = self.skill_loader.load_selected_instructions(
            query, ethical_mode=self.ethical_mode
        )
        preferences = self.memory.load_preferences()
        recent_searches = self.memory.recent_searches()
        compact_memory = self.memory.load_compact_context()
        self.heartbeat.write(
            "running",
            query=query,
            ethical_mode=self.ethical_mode,
            active_skills=list(active_skills.keys()),
        )

        if self.compact_memory_enabled and len(recent_searches) >= 2:
            compact_memory = self._compact_search_memory(
                previous_summary=compact_memory,
                recent_searches=recent_searches,
            )

        if self.clarify_ambiguous:
            clarification = self._check_ambiguity(query, compact_memory)
            if clarification.get("needs_clarification"):
                state.actions.append("ASK_CLARIFICATION")
                state.stop_reason = "needs_clarification"
                result = {
                    "query": state.original_query,
                    "ethical_mode": self.ethical_mode,
                    "locale": self.locale.to_dict(),
                    "active_skills": list(active_skills.keys()),
                    "search_queries": [],
                    "actions": state.actions,
                    "stop_reason": state.stop_reason,
                    "api_budget": self.api_budget.to_dict(),
                    "needs_clarification": True,
                    "clarifying_question": clarification.get("question"),
                    "clarification_reason": clarification.get("reason"),
                    "compact_memory": compact_memory,
                    "products": [],
                }
                self.heartbeat.write(
                    "idle",
                    last_query=query,
                    ethical_mode=self.ethical_mode,
                    last_actions=state.actions,
                    last_stop_reason=state.stop_reason,
                    products_returned=0,
                )
                return result

        for step in range(self.max_steps):
            state.actions.append(SEARCH_WEB)
            state.search_queries.append(state.current_query)
            self.heartbeat.write(
                "searching",
                query=query,
                step=step + 1,
                current_query=state.current_query,
                actions=state.actions,
            )
            new_products = self.search_tool.search(state.current_query, limit=self.result_limit)
            if self.ethical_mode:
                state.actions.append("LOOKUP_ETHICS")
                self._attach_ethics(new_products, state.current_query)
            state.products = self.reranker.top_k(
                state.products + new_products,
                self.result_limit,
                ethical_mode=self.ethical_mode,
            )

            decision = self.policy.decide_after_search(state, step, self.max_steps)
            if decision.action == STOP:
                state.actions.append(STOP)
                state.stop_reason = decision.reason
                break

            if decision.action == REFINE_QUERY:
                state.actions.append(REFINE_QUERY)
                state.remember_previous()
                try:
                    state.current_query = self._refine_query(
                        state,
                        active_skills=active_skills,
                        preferences=preferences,
                        recent_searches=recent_searches,
                        compact_memory=compact_memory,
                    )
                except ApiBudgetExceeded:
                    state.stop_reason = "api_budget_exhausted"
                    state.actions.append(STOP)
                    break

        final_products = self.reranker.top_k(
            state.products,
            self.result_limit,
            ethical_mode=self.ethical_mode,
        )
        state.actions.append(RERANK_PRODUCTS)
        result = {
            "query": state.original_query,
            "ethical_mode": self.ethical_mode,
            "locale": self.locale.to_dict(),
            "active_skills": list(active_skills.keys()),
            "search_queries": state.search_queries,
            "actions": state.actions,
            "stop_reason": state.stop_reason,
            "api_budget": self.api_budget.to_dict(),
            "needs_clarification": False,
            "compact_memory": compact_memory,
            "products": [
                product.to_dict(rank=index)
                for index, product in enumerate(final_products, start=1)
            ],
        }
        self.memory.append_search(result)
        self.heartbeat.write(
            "idle",
            last_query=query,
            ethical_mode=self.ethical_mode,
            last_actions=state.actions,
            last_stop_reason=state.stop_reason,
            products_returned=len(final_products),
        )
        return result

    def _refine_query(
        self,
        state: SearchState,
        active_skills: dict[str, str],
        preferences: dict,
        recent_searches: list[dict],
        compact_memory: dict,
    ) -> str:
        candidates = json.dumps(
            [product.to_dict(rank=index) for index, product in enumerate(state.products[:5], start=1)],
            indent=2,
        )
        agent_context = self.context_builder.build(
            state=state,
            skills=active_skills,
            preferences=preferences,
            recent_searches=recent_searches,
            compact_memory=compact_memory,
        )
        prompt = QUERY_REFINEMENT_PROMPT.format(
            agent_context=agent_context,
            original_query=state.original_query,
            current_query=state.current_query,
            candidates=candidates,
        )
        text = create_chat_text(
            self.client,
            self.model,
            prompt,
            budget=self.api_budget,
            label="refine_query",
        )
        data = loads_model_json(text)
        refined = str(data.get("refined_query") or state.current_query).strip()
        return refined or state.current_query

    def _check_ambiguity(self, query: str, compact_memory: dict) -> dict:
        try:
            text = create_chat_text(
                self.client,
                self.model,
                AMBIGUITY_CHECK_PROMPT.format(
                    query=query,
                    locale_context=self.locale.to_prompt_context(),
                    memory_summary=json.dumps(compact_memory, indent=2),
                ),
                budget=self.api_budget,
                label="check_ambiguity",
            )
            data = loads_model_json(text)
        except ApiBudgetExceeded:
            return {"needs_clarification": False, "question": None, "reason": "API budget exhausted."}
        return {
            "needs_clarification": bool(data.get("needs_clarification")),
            "question": data.get("question"),
            "reason": data.get("reason"),
        }

    def _compact_search_memory(
        self,
        previous_summary: dict,
        recent_searches: list[dict],
    ) -> dict:
        try:
            text = create_chat_text(
                self.client,
                self.model,
                MEMORY_COMPACTION_PROMPT.format(
                    previous_summary=json.dumps(previous_summary, indent=2),
                    recent_searches=json.dumps(recent_searches[-10:], indent=2),
                ),
                budget=self.api_budget,
                label="compact_memory",
            )
            data = loads_model_json(text)
        except ApiBudgetExceeded:
            return previous_summary
        self.memory.save_compact_context(data)
        return self.memory.load_compact_context()

    def _attach_ethics(self, products, query: str) -> None:
        if self.ethics_lookup is None:
            return
        for product in products:
            if not product.brand:
                product.brand = brand_for_product(
                    query=query,
                    title=product.title,
                    url=product.url,
                    source=product.source,
                )
            product.ethics = self.ethics_lookup.lookup(
                product.brand,
                product_title=product.title,
                product_url=product.url,
                product_source=product.source,
            )
