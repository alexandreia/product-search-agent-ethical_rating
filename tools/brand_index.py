"""Local Good On You brand-slug index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


BRAND_INDEX_PATH = Path(__file__).resolve().parents[1] / "data" / "good_on_you_brands.json"


@dataclass(frozen=True)
class BrandEntry:
    display_name: str
    slug: str
    match_terms: list[str]


def load_brand_index(path: Path = BRAND_INDEX_PATH) -> list[BrandEntry]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        BrandEntry(
            display_name=item["display_name"],
            slug=item["slug"],
            match_terms=[term.lower() for term in item.get("match_terms", [])],
        )
        for item in data.values()
    ]


def find_brand_entry(text: str, entries: list[BrandEntry] | None = None) -> BrandEntry | None:
    lowered = text.lower()
    sorted_entries = sorted(
        entries or load_brand_index(),
        key=lambda entry: max((len(term) for term in entry.match_terms), default=0),
        reverse=True,
    )
    for entry in sorted_entries:
        if any(term in lowered for term in entry.match_terms):
            return entry
    return None


def find_brand_entry_by_name(name: str, entries: list[BrandEntry] | None = None) -> BrandEntry | None:
    normalized = " ".join(name.lower().split())
    for entry in entries or load_brand_index():
        if normalized == entry.display_name.lower() or normalized == entry.slug:
            return entry
    return None
