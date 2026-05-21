## Product Search Agent (+ ethical rating from Good on You)

HuggingFace Space: https://huggingface.co/spaces/andreiaalexa/product-search-agent-ethical-rating

Video walkthrough: https://drive.google.com/file/d/1PEkEINxOjBgmkoqh0_Fkmzdw8WWw7i82/view?usp=sharing 

## 1. The Big Picture

```mermaid
flowchart LR
    U["User query"] --> UI["Streamlit UI or CLI"]
    UI --> A["Product Search Agent"]
    A --> M["Memory"]
    A --> S["Skills"]
    A --> W["Web retrieval"]
    A --> E["Ethics retrieval"]
    A --> R["Reranker"]
    R --> O["Top product results"]
```

The agent is not just a chatbot. It is a small retrieval system wrapped in an
agent loop. It searches, checks context, improves the query, retrieves again
when needed, and returns ranked products.

## 2. What Happens When You Search

```mermaid
flowchart TD
    Q["Query: waterproof shoes"] --> C{"Ambiguous?"}
    C -- "Yes" --> D["Ask clarification"]
    D --> E1["Edit query"]
    D --> E2["Search anyway"]
    C -- "No" --> L["Load skills + memory"]
    E1 --> Q
    E2 --> L
    L --> W["Search web"]
    W --> P["Parse product candidates"]
    P --> G{"Ethical mode?"}
    G -- "Yes" --> GOY["Retrieve Good On You rating"]
    G -- "No" --> RK["Rerank products"]
    GOY --> RK
    RK --> STOP{"Stop or refine?"}
    STOP -- "Refine" --> REF["LLM creates better search query"]
    REF --> W
    STOP -- "Stop" --> OUT["Return top results"]
```

The agent can pause before retrieval if the query is too vague. In the UI, this
appears as a popup with two choices:

- **Edit query**: go back and make the query clearer.
- **Search anyway**: skip clarification and retrieve with the original query.

## 3. Where The LLM Is Used

```mermaid
flowchart LR
    LLM["LLM"] --> A["Ambiguity check"]
    LLM --> B["Query refinement"]
    LLM --> C["Product extraction from snippets"]
    LLM --> D["Memory compaction"]

    F["Facts from retrieval"] --> R["Final result"]
    A --> R
    B --> R
    C --> R
    D --> R
```

The LLM is used as a controller and context engineer. It helps the agent decide
how to search better, but it should not invent facts.

Good LLM uses in this project:

- Decide whether a query is too ambiguous.
- Rewrite a weak search query into a better retrieval query.
- Extract structured products from search result snippets.
- Compact past searches into useful memory.

Things the LLM should not decide:

- Good On You ratings.
- Whether a brand exists in Good On You.
- Product prices or availability.
- Source URLs.

Those facts must come from retrieval.

## 4. Information Retrieval Actions

```mermaid
stateDiagram-v2
    [*] --> CHECK_AMBIGUITY
    CHECK_AMBIGUITY --> ASK_CLARIFICATION: vague query
    CHECK_AMBIGUITY --> SEARCH_WEB: clear enough
    ASK_CLARIFICATION --> SEARCH_WEB: user skips or edits
    SEARCH_WEB --> LOOKUP_ETHICS: ethical mode on
    SEARCH_WEB --> RERANK_PRODUCTS: ethical mode off
    LOOKUP_ETHICS --> RERANK_PRODUCTS
    RERANK_PRODUCTS --> REFINE_QUERY: weak results
    REFINE_QUERY --> SEARCH_WEB
    RERANK_PRODUCTS --> STOP: enough results or repeated state
    STOP --> [*]
```

The agent uses actions as retrieval steps:

| Action | Purpose |
| --- | --- |
| `ASK_CLARIFICATION` | Stop early if the query is too vague. |
| `SEARCH_WEB` | Retrieve real product candidates from the live web. |
| `LOOKUP_ETHICS` | Retrieve Good On You brand ratings when ethical mode is on. |
| `REFINE_QUERY` | Improve the retrieval query based on current context. |
| `RERANK_PRODUCTS` | Sort and deduplicate candidates. |
| `STOP` | Stop when results are good enough, budget is exhausted, or the state repeats. |

## 5. Memory System

```mermaid
flowchart TD
    H["search_history.jsonl"] --> MC["LLM memory compaction"]
    P["user_preferences.json"] --> CTX["Context builder"]
    MC --> CC["compact_context.json"]
    CC --> CTX
    EC["brand_ethics_cache.json"] --> ETH["Ethics lookup"]
    CTX --> PROMPT["Refinement + ambiguity prompts"]
```

The memory system has three jobs:

- **Search history** keeps a log of past runs.
- **Compacted memory** summarizes useful patterns from past searches.
- **Ethics cache** avoids retrieving the same Good On You brand page repeatedly.

Example compact memory:

```json
{
  "summary": "The user often searches for outdoor products in Sweden with SEK prices.",
  "retrieval_preferences": [
    "Prefer Swedish or EU product pages when country is Sweden.",
    "Prefer product pages over generic category pages."
  ],
  "avoid": [
    "Do not treat blog roundups as product pages unless they name concrete products."
  ]
}
```

## 6. Ethical Mode

```mermaid
flowchart LR
    P["Product candidate"] --> B["Resolve brand"]
    B --> I["Local brand index"]
    I --> URL["Good On You brand URL"]
    URL --> PAGE["Retrieve brand page"]
    PAGE --> PARSE["Parse rating"]
    PARSE --> CACHE["Cache rating"]
    CACHE --> SCORE["Soft reranking boost"]
```

Ethical mode does not remove products. It keeps all products and adds brand
rating context when available.

Important rule:

> The agent does not infer Good On You ratings with the LLM.

The rating must come from the retrieved Good On You brand page. If the brand is
not found, the agent says it is not rated instead of guessing.

## 7. API Budget

```mermaid
flowchart TD
    B["API budget"] --> A["Ambiguity check"]
    B --> M["Memory compaction"]
    B --> X["Product extraction"]
    B --> R["Query refinement"]
    A -->|"budget exhausted"| F["Skip optional LLM step"]
    M -->|"budget exhausted"| F
    R -->|"budget exhausted"| S["Stop with api_budget_exhausted"]
```

The API budget makes demos safer. If the budget is low, the agent still tries
to continue with deterministic fallbacks where possible.

Example:

```bash
python main.py "waterproof hiking shoes under 1500 SEK" \
  --model "google/gemma-4-31B-it" \
  --country Sweden \
  --market se-sv \
  --currency SEK \
  --max-api-calls 3
```

## 8. UI Walkthrough

```mermaid
flowchart TD
    UI["Product Search Agent page"] --> Q["Main query input"]
    UI --> SET["Sidebar settings"]
    SET --> ETH["Ethical mode"]
    SET --> LOC["Country / market / currency"]
    SET --> BUD["API call budget"]
    SET --> MEM["Memory panel"]
    Q --> RUN["Search"]
    RUN --> POP{"Clarification popup?"}
    POP -- "Edit query" --> Q
    POP -- "Search anyway" --> RES["Top products"]
    POP -- "No popup" --> RES
    RES --> TRACE["Agent Trace"]
    RES --> HB["Heartbeat"]
```

The Streamlit page is designed for demonstrating the agent:

- The main input is the only query input.
- Ambiguous searches open a popup instead of adding another text field.
- The sidebar controls retrieval behavior.
- The agent trace shows what actions were taken.
- The heartbeat shows the latest run status.

## 9. Example Demo Script

Use this for a short presentation.

1. Start the UI:

```bash
streamlit run app.py
```

2. Try an ambiguous query:

```text
waterproof shoes
```

Show that the agent asks for clarification before retrieval.

3. Click **Search anyway**.

Show that the agent can continue even when the user skips the question.

4. Try a clearer localized query:

```text
waterproof hiking shoes under 1500 SEK
```

Show:

- Locale: Sweden / `se-sv` / SEK.
- Search queries used.
- Top ranked product candidates.
- Agent trace.

5. Turn on ethical mode and search:

```text
HOKA waterproof hiking shoes
```

Show:

- Brand resolution.
- Good On You source URL.
- Rating shown without filtering products out.

## 10. One-Slide Summary

```mermaid
flowchart LR
    Q["User need"] --> IR["IR actions"]
    IR --> C["Better context"]
    C --> L["LLM reasoning"]
    L --> IR
    IR --> T["Top products"]

    subgraph RS["Retrieval system"]
        W["Web search"]
        E["Ethics lookup"]
        M["Memory"]
        R["Reranking"]
    end
```

The project shows how an AI agent can improve Information Retrieval by
combining live search, memory, query refinement, skills, ethical retrieval, and
state-based stopping.
