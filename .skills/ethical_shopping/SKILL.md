---
name: ethical_shopping
description: Use when ethical mode is enabled or the user asks for ethical, sustainable, responsible, fair, or conscious shopping.
---

# Ethical Shopping

When this skill is active:

1. Keep all retrieved products in the candidate set.
2. Check product brands against Good On You.
3. If a brand is rated, attach the Good On You rating and source URL.
4. If a brand is not found, mark it as `not_rated`.
5. Do not infer, guess, or invent ethical ratings.
6. Softly boost better-rated brands during reranking, but do not filter products.
7. Phrase ratings as source-specific: "Good On You rates this brand as X."

