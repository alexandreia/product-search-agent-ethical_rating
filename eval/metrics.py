"""Lightweight trace metrics for the product search agent."""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize agent traces across demo queries."""
    action_counts: Counter[str] = Counter()
    stop_reasons: Counter[str] = Counter()
    product_counts = []

    for run in runs:
        action_counts.update(run.get("actions", []))
        stop_reasons[run.get("stop_reason", "unknown")] += 1
        product_counts.append(len(run.get("products", [])))

    return {
        "runs": len(runs),
        "action_counts": dict(action_counts),
        "stop_reasons": dict(stop_reasons),
        "mean_products_returned": (
            sum(product_counts) / len(product_counts) if product_counts else 0.0
        ),
    }
