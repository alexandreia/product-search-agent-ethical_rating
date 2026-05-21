"""File-backed memory for preferences, search history, and ethics cache."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema.ethics import EthicsRating


ETHICS_CACHE_VERSION = 2


class MemoryManager:
    """Small persistent memory layer for the agent."""

    def __init__(self, memory_dir: str | Path = "memory") -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.preferences_path = self.memory_dir / "user_preferences.json"
        self.history_path = self.memory_dir / "search_history.jsonl"
        self.compact_context_path = self.memory_dir / "compact_context.json"
        self.ethics_cache_path = self.memory_dir / "brand_ethics_cache.json"
        self._ensure_defaults()

    def load_preferences(self) -> dict[str, Any]:
        return _read_json(self.preferences_path, default={})

    def recent_searches(self, limit: int = 5) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        rows = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows[-limit:]

    def append_search(self, result: dict[str, Any]) -> None:
        row = {
            "timestamp": _utc_now(),
            "query": result.get("query"),
            "ethical_mode": result.get("ethical_mode"),
            "search_queries": result.get("search_queries", []),
            "actions": result.get("actions", []),
            "stop_reason": result.get("stop_reason"),
            "products_returned": len(result.get("products", [])),
        }
        with self.history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row) + "\n")

    def load_compact_context(self) -> dict[str, Any]:
        return _read_json(
            self.compact_context_path,
            default={
                "summary": "",
                "retrieval_preferences": [],
                "avoid": [],
                "last_updated_reason": "",
            },
        )

    def save_compact_context(self, data: dict[str, Any]) -> None:
        compacted = {
            "updated_at": _utc_now(),
            "summary": str(data.get("summary") or "").strip(),
            "retrieval_preferences": [
                str(item).strip()
                for item in data.get("retrieval_preferences", [])
                if str(item).strip()
            ],
            "avoid": [
                str(item).strip()
                for item in data.get("avoid", [])
                if str(item).strip()
            ],
            "last_updated_reason": str(data.get("last_updated_reason") or "").strip(),
        }
        _write_json(self.compact_context_path, compacted)

    def get_ethics_rating(self, brand_key: str) -> EthicsRating | None:
        cache = _read_json(self.ethics_cache_path, default={})
        if cache.get("_version") != ETHICS_CACHE_VERSION:
            return None
        data = cache.get(brand_key)
        if not data:
            return None
        return EthicsRating(
            source=data.get("source", "Good On You"),
            status=data.get("status", "not_rated"),
            rating=data.get("rating"),
            score=float(data.get("score", 0.0)),
            source_url=data.get("source_url", "https://directory.goodonyou.eco/"),
            note=data.get("note", ""),
        )

    def set_ethics_rating(self, brand_key: str, rating: EthicsRating) -> None:
        cache = _read_json(self.ethics_cache_path, default={})
        if cache.get("_version") != ETHICS_CACHE_VERSION:
            cache = {"_version": ETHICS_CACHE_VERSION}
        cache[brand_key] = asdict(rating)
        _write_json(self.ethics_cache_path, cache)

    def _ensure_defaults(self) -> None:
        if not self.preferences_path.exists():
            _write_json(
                self.preferences_path,
                {
                    "ethical_mode_default": False,
                    "preferred_currency": None,
                    "preferred_sources": [],
                    "avoid_sources": [],
                },
            )
        if not self.ethics_cache_path.exists():
            _write_json(self.ethics_cache_path, {})
        if not self.compact_context_path.exists():
            self.save_compact_context({})
        if not self.history_path.exists():
            self.history_path.touch()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
