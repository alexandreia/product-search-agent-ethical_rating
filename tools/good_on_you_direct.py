"""Direct Good On You brand-page lookup helpers."""

from __future__ import annotations

import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from schema.ethics import EthicsRating
from tools.brand_index import find_brand_entry


def brand_slug(brand: str) -> str:
    entry = find_brand_entry(brand)
    if entry is not None:
        return entry.slug
    normalized = re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-")
    return re.sub(r"-+", "-", normalized)


def direct_good_on_you_lookup(brand: str) -> EthicsRating:
    slug = brand_slug(brand)
    if not slug:
        return EthicsRating.not_rated(brand)

    source_url = f"https://directory.goodonyou.eco/brand/{slug}"
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError):
        return EthicsRating.not_rated(brand)

    rating = extract_rating_from_good_on_you_html(html)
    if rating is None:
        return EthicsRating.not_rated(brand)
    return EthicsRating.rated(rating=rating, source_url=source_url)


def extract_rating_from_good_on_you_html(html: str) -> str | None:
    text = good_on_you_brand_scope(unescape(html))
    patterns = [
        r"Rated\s*:?\s*(Great|Good|It['’]s a start|Not good enough|We avoid)",
        r"Overall rating\s*:?\s*(Great|Good|It['’]s a start|Not good enough|We avoid)",
        r"rate\s+[^<]{0,80}\s+[“\"]([^”\"]+)[”\"]\s+overall",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            rating = normalize_rating(match.group(1))
            if rating:
                return rating
    return None


def good_on_you_brand_scope(text: str) -> str:
    """Keep the parser focused on the current brand, not recommendation cards."""
    scope = text
    section_markers = [
        "Similar brands",
        "You may also like",
        "More from",
        "Explore brands",
    ]
    for marker in section_markers:
        index = scope.lower().find(marker.lower())
        if index != -1:
            scope = scope[:index]
    return scope[:50000]


def normalize_rating(value: str) -> str | None:
    cleaned = " ".join(value.replace("&amp;", "&").split()).strip(" .")
    known = {
        "great": "Great",
        "good": "Good",
        "it's a start": "It's a start",
        "it’s a start": "It's a start",
        "not good enough": "Not good enough",
        "we avoid": "We avoid",
    }
    return known.get(cleaned.lower())
