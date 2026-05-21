"""Taxonomy hints for general product search.

The agent uses public product-taxonomy concepts rather than a hand-maintained
catalog. Shopify taxonomy is useful for category-aware attributes; Google
taxonomy is useful as a broad product category vocabulary.
"""

SHOPIFY_TAXONOMY_URL = "https://shopify.github.io/product-taxonomy/releases/2024-07/"
GOOGLE_TAXONOMY_URL = "https://www.google.com/basepages/producttype/taxonomy.en-US.txt"

TAXONOMY_HINTS = {
    "category": "Infer a broad-to-specific product category path.",
    "attributes": "Infer category-specific attributes that affect relevance.",
    "constraints": "Preserve price, size, compatibility, color, material, and availability constraints.",
}

