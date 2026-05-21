"""Deterministic brand resolution from retrieved metadata."""

from __future__ import annotations

from urllib.parse import urlparse

from tools.brand_index import find_brand_entry


def brand_for_product(query: str, title: str, url: str, source: str) -> str | None:
    """Resolve a brand using only explicit retrieved metadata.

    Query text is intentionally ignored here. A brand is returned only from the
    retrieved title/source/domain/URL, or from the source prefix before a dot.
    """
    text = _combined_text(title, url, source)
    entry = find_brand_entry(text)
    if entry:
        return entry.display_name
    return brand_from_source(source=source, url=url)


def brand_from_source(source: str, url: str = "") -> str | None:
    parsed = urlparse(url)
    host = (source or parsed.netloc).lower()
    if not host:
        return None
    host = host.replace("www.", "").strip()
    prefix = host.split(".", 1)[0].strip("-_ ")
    if not prefix:
        return None
    return _display_name_from_domain_prefix(prefix)


def _combined_text(title: str, url: str, source: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc or source
    return f"{title} {url} {source} {domain}".lower()


def _display_name_from_domain_prefix(prefix: str) -> str:
    overrides = {
        "adidas": "Adidas",
        "hoka": "HOKA",
        "championstore": "Champion",
    }
    if prefix in overrides:
        return overrides[prefix]
    return prefix.replace("-", " ").title()
