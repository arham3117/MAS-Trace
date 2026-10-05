"""Model provider interface (plan.md P2.1)."""

from __future__ import annotations

from typing import Protocol

from mastrace.core.schemas import ModelRequest, ModelResponse


class ModelProvider(Protocol):
    """Anything that can answer a `ModelRequest`. Only the model gateway calls providers."""

    name: str
    identity: str  # names the model *and* its behaviour; part of every request hash

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return the model's answer to `request`."""
        ...


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate (~4 characters per token)."""
    return (len(text) + 3) // 4
