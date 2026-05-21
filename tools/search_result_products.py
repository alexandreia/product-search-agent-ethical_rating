"""Convert generic web search results into product candidates."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse, unquote

from schema.product import Product
from schema.locale import SearchLocale
from tools.duckduckgo_search import SearchResult


def product_from_search_result(
    result: SearchResult,
    query: str,
    locale: SearchLocale | None = None,
) -> Product:
    clean_url = normalize_result_url(result.url)
    return Product(
        title=result.title,
        url=clean_url,
        source=source_from_url(clean_url),
        relevance_score=relevance_score(query, result, clean_url, locale),
        reason="Candidate product result from live web search. Details should be checked on the linked page.",
    )


def normalize_result_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return unquote(query["uddg"][0])
    return url


def source_from_url(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0].replace("www.", "")


def relevance_score(
    query: str,
    result: SearchResult,
    url: str,
    locale: SearchLocale | None = None,
) -> float:
    lexical = lexical_score(query, f"{result.title} {result.snippet}")
    adjustment = source_quality_adjustment(result.title, url)
    adjustment += locale_adjustment(result.title, result.snippet, url, locale)
    return max(0.05, min(0.95, lexical + adjustment))


def lexical_score(query: str, text: str) -> float:
    query_terms = {term.lower() for term in query.split() if len(term) > 2}
    if not query_terms:
        return 0.3
    text_lower = text.lower()
    matched = sum(1 for term in query_terms if term in text_lower)
    return min(0.8, 0.35 + 0.45 * (matched / len(query_terms)))


def source_quality_adjustment(title: str, url: str) -> float:
    lowered = f"{title} {url}".lower()
    article_terms = ["best ", "top picks", "guide", "review", "tested", "archives"]
    retailer_terms = [
        "zappos.com",
        "rei.com",
        "backcountry.com",
        "dickssportinggoods.com",
        "footlocker.com",
        "amazon.com",
        "walmart.com",
        "target.com",
        "shop",
        "product",
        "collections",
        "buy",
    ]
    adjustment = 0.0
    if any(term in lowered for term in retailer_terms):
        adjustment += 0.08
    if any(term in lowered for term in article_terms):
        adjustment -= 0.12
    return adjustment


def locale_adjustment(title: str, snippet: str, url: str, locale: SearchLocale | None) -> float:
    if locale is None:
        return 0.0

    lowered = f"{title} {snippet} {url}".lower()
    adjustment = 0.0
    country = locale.country.lower()
    currency = locale.currency.lower()
    market_country = locale.market.split("-", 1)[0].lower()

    if country and country in lowered:
        adjustment += 0.06
    if currency and currency in lowered:
        adjustment += 0.06
    if market_country == "se" and (".se/" in lowered or lowered.endswith(".se")):
        adjustment += 0.08
    if market_country == "uk" and (".co.uk" in lowered or ".uk/" in lowered):
        adjustment += 0.08
    if market_country == "de" and ".de/" in lowered:
        adjustment += 0.08
    return adjustment
