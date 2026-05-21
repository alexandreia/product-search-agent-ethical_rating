"""Streamlit UI for the taxonomy-aware product search agent."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from agent.memory import MemoryManager
from agent.shopping_agent import ShoppingSearchAgent


st.set_page_config(
    page_title="Product Search Agent",
    page_icon="",
    layout="wide",
)


def main() -> None:
    if "query" not in st.session_state:
        st.session_state.query = "waterproof hiking shoes under $150"
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    st.title("Product Search Agent")
    st.caption("Real product search with retrieval, skills, memory, and optional ethical reranking.")
    with st.expander("What this agent can do", expanded=False):
        st.markdown(
            """
            - Searches the live web for real product candidates and reranks the top results.
            - Refines weak searches with product taxonomy terms, constraints, and locale hints.
            - Uses memory from past searches to improve future retrieval context.
            - Can pause and ask a clarifying question before searching if a query is too ambiguous.
            - Ethical mode keeps all products but adds Good On You ratings when a brand is found.
            """
        )

    with st.sidebar:
        st.header("Agent Settings")
        model = st.text_input("Model", value="google/gemma-4-31B-it")
        max_steps = st.slider("Max search/refine steps", min_value=1, max_value=5, value=3)
        result_limit = st.slider("Products to return", min_value=3, max_value=15, value=10)
        max_api_calls = st.slider("API call budget", min_value=0, max_value=10, value=3)
        ethical_mode = st.toggle("Ethical mode", value=False)
        clarify_ambiguous = st.toggle("Ask before ambiguous searches", value=True)
        compact_memory = st.toggle("Compact past searches into memory", value=True)
        st.divider()
        st.subheader("Search Locale")
        country = st.text_input("Country", value="Sweden")
        market = st.selectbox(
            "Market",
            options=["se-sv", "us-en", "uk-en", "de-de", "fr-fr", "dk-da", "no-no"],
            index=0,
        )
        currency = st.text_input("Currency", value="SEK")

        st.divider()
        st.subheader("Memory")
        memory = MemoryManager()
        recent = memory.recent_searches(limit=10)
        if recent:
            st.caption("Click a past search to reuse it.")
            for index, row in enumerate(reversed(recent)):
                label = _history_label(row)
                if st.button(label, key=f"history_{index}", use_container_width=True):
                    st.session_state.query = row.get("query") or ""
                    st.rerun()
            with st.expander("View raw search history", expanded=False):
                st.json(list(reversed(recent)))
        else:
            st.caption("No search history yet.")
        compact = memory.load_compact_context()
        if compact.get("summary"):
            with st.expander("Compacted memory", expanded=False):
                st.json(compact)

    query = st.text_input(
        "What are you looking for?",
        key="query",
        placeholder="e.g. quiet mechanical keyboard for Mac under $120",
    )

    col_a, col_b = st.columns([1, 4])
    with col_a:
        search_clicked = st.button("Search", type="primary", use_container_width=True)
    with col_b:
        st.caption("Use single, specific product queries for best results.")

    if search_clicked:
        if not query.strip():
            st.warning("Enter a query first.")
            return

        result = run_agent_search(
            query=query.strip(),
            model=model,
            max_steps=max_steps,
            result_limit=result_limit,
            ethical_mode=ethical_mode,
            max_api_calls=max_api_calls,
            country=country,
            market=market,
            currency=currency,
            clarify_ambiguous=clarify_ambiguous,
            compact_memory=compact_memory,
        )
        if result is None:
            return
        st.session_state.last_result = result

    result = st.session_state.last_result
    if result:
        render_summary(result)
        if result.get("needs_clarification"):
            render_clarification_dialog(
                result=result,
                model=model,
                max_steps=max_steps,
                result_limit=result_limit,
                ethical_mode=ethical_mode,
                max_api_calls=max_api_calls,
                country=country,
                market=market,
                currency=currency,
                compact_memory=compact_memory,
            )
        else:
            render_products(result.get("products", []), ethical_mode=ethical_mode)
        if not result.get("needs_clarification"):
            render_diagnostics(result)
            render_heartbeat()


@st.dialog("Clarify search")
def render_clarification_dialog(
    *,
    result: dict,
    model: str,
    max_steps: int,
    result_limit: int,
    ethical_mode: bool,
    max_api_calls: int,
    country: str,
    market: str,
    currency: str,
    compact_memory: bool,
) -> None:
    st.write(result.get("clarifying_question") or "The agent needs clarification before searching.")
    if result.get("clarification_reason"):
        st.caption(result["clarification_reason"])

    st.divider()
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Edit query", type="primary", use_container_width=True):
            st.session_state.query = result.get("query", "")
            st.session_state.last_result = None
            st.rerun()
    with col_b:
        if st.button("Search anyway", use_container_width=True):
            next_result = run_agent_search(
                query=result.get("query", ""),
                model=model,
                max_steps=max_steps,
                result_limit=result_limit,
                ethical_mode=ethical_mode,
                max_api_calls=max_api_calls,
                country=country,
                market=market,
                currency=currency,
                clarify_ambiguous=False,
                compact_memory=compact_memory,
            )
            if next_result is not None:
                st.session_state.last_result = next_result
                st.rerun()


def render_summary(result: dict) -> None:
    if result.get("needs_clarification"):
        return
    budget = result.get("api_budget") or {}
    cols = st.columns(4)
    cols[0].metric("Products", len(result.get("products", [])))
    cols[1].metric("API calls", budget.get("used_calls", 0))
    cols[2].metric("Stop reason", result.get("stop_reason") or "unknown")
    cols[3].metric("Ethical mode", "On" if result.get("ethical_mode") else "Off")
    locale = result.get("locale") or {}
    st.caption(
        f"Locale: {locale.get('country', 'unknown')} · "
        f"{locale.get('market', 'unknown')} · {locale.get('currency', 'unknown')}"
    )

    if result.get("stop_reason") == "api_budget_exhausted":
        st.info("The API budget was exhausted, so the agent used deterministic fallback results where possible.")


def run_agent_search(
    *,
    query: str,
    model: str,
    max_steps: int,
    result_limit: int,
    ethical_mode: bool,
    max_api_calls: int,
    country: str,
    market: str,
    currency: str,
    clarify_ambiguous: bool,
    compact_memory: bool,
) -> dict | None:
    with st.spinner("Searching, refining, and reranking products..."):
        try:
            agent = ShoppingSearchAgent(
                model=model,
                max_steps=max_steps,
                result_limit=result_limit,
                ethical_mode=ethical_mode,
                max_api_calls=max_api_calls,
                country=country,
                market=market,
                currency=currency,
                clarify_ambiguous=clarify_ambiguous,
                compact_memory=compact_memory,
            )
            return agent.run(query)
        except Exception as exc:
            st.error(str(exc))
            return None

def _history_label(row: dict) -> str:
    query = row.get("query") or "Untitled search"
    products = row.get("products_returned", 0)
    mode = "ethical" if row.get("ethical_mode") else "standard"
    return f"{query} · {products} products · {mode}"


def render_products(products: list[dict], ethical_mode: bool) -> None:
    st.subheader("Top Products")
    if not products:
        st.warning("No products were returned. Try a broader query or a larger API budget.")
        return

    for product in products:
        with st.container(border=True):
            top = st.columns([5, 1])
            with top[0]:
                title = product.get("title") or "Untitled product"
                url = product.get("url") or ""
                if url:
                    st.markdown(f"### [{product.get('rank')}. {title}]({url})")
                else:
                    st.markdown(f"### {product.get('rank')}. {title}")
                meta = []
                if product.get("brand"):
                    meta.append(f"Brand: {product['brand']}")
                if product.get("source"):
                    meta.append(f"Source: {product['source']}")
                if product.get("price"):
                    meta.append(f"Price: {product['price']}")
                if meta:
                    st.caption(" · ".join(meta))
            with top[1]:
                st.metric("Relevance", product.get("relevance_score", 0))

            if product.get("reason"):
                st.write(product["reason"])

            if ethical_mode:
                render_ethics(product.get("ethics"))


def render_ethics(ethics: dict | None) -> None:
    if not ethics:
        st.caption("Ethics: no brand rating available.")
        return

    status = ethics.get("status")
    rating = ethics.get("rating")
    source_url = ethics.get("source_url")
    if status == "rated":
        st.success(f"Good On You rating: {rating}")
        if source_url:
            st.caption(f"Source: {source_url}")
    else:
        st.caption(ethics.get("note") or "Brand was not found in Good On You.")


def render_diagnostics(result: dict) -> None:
    with st.expander("Agent Trace", expanded=False):
        st.write("Active skills")
        st.code("\n".join(result.get("active_skills", [])) or "None")
        st.write("Actions")
        st.code(" -> ".join(result.get("actions", [])) or "None")
        st.write("Search queries")
        st.json(result.get("search_queries", []))
        st.write("API budget")
        st.json(result.get("api_budget", {}))
        if result.get("compact_memory"):
            st.write("Compacted memory")
            st.json(result["compact_memory"])


def render_heartbeat() -> None:
    heartbeat_path = Path("heartbeat/heartbeat.json")
    if not heartbeat_path.exists():
        return
    with st.expander("Heartbeat", expanded=False):
        st.json(json.loads(heartbeat_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
