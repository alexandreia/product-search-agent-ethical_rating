"""Per-run API call budget."""

from __future__ import annotations

from dataclasses import dataclass


class ApiBudgetExceeded(RuntimeError):
    """Raised when an LLM/API call would exceed the configured budget."""


@dataclass
class ApiBudget:
    """Tracks how many provider API calls the agent may make in one run."""

    max_calls: int | None = None
    used_calls: int = 0

    def consume(self, label: str) -> None:
        if self.max_calls is not None and self.used_calls >= self.max_calls:
            raise ApiBudgetExceeded(f"API call budget exhausted before {label}.")
        self.used_calls += 1

    def to_dict(self) -> dict:
        return {
            "max_calls": self.max_calls,
            "used_calls": self.used_calls,
            "remaining_calls": None
            if self.max_calls is None
            else max(0, self.max_calls - self.used_calls),
        }

