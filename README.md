# E-commerce Product Search Agent with ethical rating (Good on You directory)

An AI agent that searches for real products on the web, improves its search
context through information retrieval actions, and returns a top-10 product
ranking for a product query.

The project is designed for an Information Retrieval lab: the agent does not
answer from model memory. It uses live web search, product-taxonomy reasoning,
query refinement, skills, persistent memory, candidate memory, reranking, and
loop stopping.

## What The Agent Does

Given a query such as:

```text
best waterproof hiking shoes under $150
```

the agent:

1. Searches the live web for product pages.
2. Extracts structured product candidates.
3. Infers product category and attributes using Shopify/Google-style taxonomy
   concepts.
4. Refines weak searches with better category or attribute terms.
5. Optionally checks brands against Good On You in soft ethical mode.
6. Deduplicates and reranks candidates.
7. Stops when it has enough relevant products or the search state repeats.
8. Returns a top-10 ranked product list with URLs and reasons.

## IR Extension

This extends a normal LLM agent with IR-style actions:

- `SEARCH_WEB`: retrieve current product context from the web.
- `REFINE_QUERY`: improve the search query using product taxonomy and observed
  candidates.
- `LOOKUP_ETHICS`: check product brands against Good On You when ethical mode
  is enabled.
- `RERANK_PRODUCTS`: sort retrieved candidates by relevance.
- `STOP`: stop when results are good enough or state equivalence detects a loop.

The agent also has:

- `.skills/`: task-specific skill instructions loaded only when relevant.
- `memory/`: preferences, search history, and cached Good On You ratings.
- `heartbeat/heartbeat.json`: current/last run status.
- `agent/context.py`: compact context builder for refinement prompts.

The taxonomy idea is inspired by:

- Shopify Product Taxonomy: <https://shopify.github.io/product-taxonomy/releases/2024-07/>
- Google Product Taxonomy: <https://www.google.com/basepages/producttype/taxonomy.en-US.txt>

## Setup

Use Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your_api_key_here"
```

Optional:

```bash
export OPENAI_BASE_URL="https://api.openai.com/v1"
export SKILLS_DIR=".skills"
```

The web search tool first tries OpenAI's Responses API `web_search` tool. If
the provider does not support `/responses`, it falls back to DuckDuckGo HTML
search plus OpenAI-compatible `chat.completions` extraction. This makes the
agent usable with providers such as Berget that expose an OpenAI-compatible
chat API.

## Run

```bash
python main.py "best waterproof hiking shoes under $150"
```

Run the Streamlit UI:

```bash
streamlit run app.py
```

With Berget, use the full provider-qualified model id shown in their model
library, for example:

```bash
python main.py "best waterproof hiking shoes under $150" --model "google/gemma-4-31B-it"
```

Limit provider API calls for a demo run:

```bash
python main.py "best waterproof hiking shoes under $150" --model "google/gemma-4-31B-it" --max-api-calls 2
```

Use geolocalized search:

```bash
python main.py "waterproof hiking shoes under 1500 SEK" \
  --model "google/gemma-4-31B-it" \
  --country Sweden \
  --market se-sv \
  --currency SEK \
  --max-api-calls 3
```

If the budget is exhausted, the agent keeps running with deterministic web
search fallbacks where possible.

Soft ethical mode keeps all products, shows Good On You ratings when available,
marks missing brands as not rated, and gives better-rated brands a small
reranking boost:

```bash
python main.py "waterproof hiking jacket under $200" --ethical-mode
```

Other examples:

```bash
python main.py "quiet mechanical keyboard for mac under $120"
python main.py "non stick frying pan induction compatible"
python main.py "lightweight carry on suitcase with spinner wheels"
```

The command prints JSON:

```json
{
  "query": "best waterproof hiking shoes under $150",
  "search_queries": ["..."],
  "actions": ["SEARCH_WEB", "STOP", "RERANK_PRODUCTS"],
  "stop_reason": "enough_relevant_products",
  "products": [
    {
      "rank": 1,
      "title": "...",
      "price": "...",
      "source": "...",
      "url": "...",
      "relevance_score": 0.91,
      "reason": "..."
    }
  ]
}
```

## Agent Walkthrough

For a visual explanation of the agent loop, memory, LLM usage, ethical mode,
and UI flow, see:

[AGENT_WALKTHROUGH.md](AGENT_WALKTHROUGH.md)

## Project Structure

```text
agent/
  shopping_agent.py   agent loop: search, refine, rerank, stop
  state.py            working memory and state equivalence
  prompts.py          structured prompts for retrieval/refinement
  reranker.py         deduplication and top-k ranking
  skill_loader.py     .skills metadata discovery and instruction loading
  memory.py           file-backed preferences, history, and ethics cache
  heartbeat.py        heartbeat status writer
  api_budget.py       per-run provider API call budget
  context.py          compact context builder

tools/
  web_product_search.py  live product retrieval through web search
  ethics_lookup.py       Good On You brand rating lookup
  brand_index.py         local brand-to-Good-On-You-slug index loader
  taxonomy.py            taxonomy source references and hints

schema/
  product.py          normalized product result schema
  ethics.py           Good On You rating schema and score mapping

.skills/
  ethical_shopping/
  taxonomy_search/
  product_reranking/

memory/
  user_preferences.json
  search_history.jsonl
  brand_ethics_cache.json

data/
  good_on_you_brands.json

heartbeat/
  heartbeat.json

eval/
  metrics.py          lightweight trace summaries

tests/
  test_core.py        offline tests for parser, policy, reranker, schema

examples/
  example_queries.md

report/
  report.md

app.py                Streamlit demo UI
```

## Notes

This is a learning-oriented agent, not a production product search engine. It depends
on live web results and model extraction quality, so product prices and
availability should be checked on the linked product pages before purchase.
Ethical mode reports Good On You ratings when the brand is found in that
directory; it does not infer ratings for brands that are missing.

## Tests

The offline unit tests do not call the OpenAI API and use Python's standard
library test runner:

```bash
python -m unittest discover -s tests
```
