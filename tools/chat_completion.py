"""OpenAI-compatible chat completion helpers."""

from __future__ import annotations

from openai import InternalServerError

from agent.api_budget import ApiBudget


def create_chat_text(
    client,
    model: str,
    prompt: str,
    budget: ApiBudget | None = None,
    label: str = "chat_completion",
) -> str:
    """Return text from an OpenAI-compatible chat.completions call."""
    if budget is not None:
        budget.consume(label)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise information retrieval assistant. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
    except InternalServerError as exc:
        message = str(exc)
        if "Model" in message and "not found" in message:
            raise RuntimeError(
                f"Model '{model}' was not found by your OpenAI-compatible provider. "
                "For Berget, use the full provider-qualified model id, for example "
                "'google/gemma-4-31B-it', or choose another model from the Berget console."
            ) from exc
        raise
    return response.choices[0].message.content or ""
