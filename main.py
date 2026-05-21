#!/usr/bin/env python3
"""Command-line entry point for the product search agent."""

from __future__ import annotations

import argparse
import json

from agent.shopping_agent import ShoppingSearchAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search real products with an IR-extended AI agent.")
    parser.add_argument("query", help="Shopping query, e.g. 'waterproof hiking shoes under $150'")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI model to use")
    parser.add_argument("--max-steps", type=int, default=3)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--max-api-calls",
        type=int,
        default=None,
        help="Maximum provider API calls for one run. If exhausted, the agent uses deterministic fallbacks.",
    )
    parser.add_argument("--skills-dir", default=None, help="Override .skills directory.")
    parser.add_argument("--country", default="United States", help="Preferred product search country.")
    parser.add_argument("--market", default="us-en", help="DuckDuckGo market/region code, e.g. us-en, se-sv, uk-en.")
    parser.add_argument("--currency", default="USD", help="Preferred currency, e.g. USD, SEK, EUR.")
    parser.add_argument(
        "--ethical-mode",
        action="store_true",
        help="Show Good On You brand ratings and softly boost better-rated brands.",
    )
    parser.add_argument(
        "--no-clarify",
        action="store_true",
        help="Skip the LLM ambiguity check and search immediately.",
    )
    parser.add_argument(
        "--no-memory-compaction",
        action="store_true",
        help="Skip LLM compaction of past searches into compact memory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = ShoppingSearchAgent(
        model=args.model,
        max_steps=args.max_steps,
        result_limit=args.limit,
        ethical_mode=args.ethical_mode,
        skills_dir=args.skills_dir,
        max_api_calls=args.max_api_calls,
        country=args.country,
        market=args.market,
        currency=args.currency,
        clarify_ambiguous=not args.no_clarify,
        compact_memory=not args.no_memory_compaction,
    )
    result = agent.run(args.query)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
