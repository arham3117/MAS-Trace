"""LiteLLM-backed provider for open-weight and commercial models (plan.md P2.1)."""

from __future__ import annotations

import os

# LiteLLM otherwise downloads its model cost map from GitHub at import time (ISSUE-010):
# a network call outside the gateways, caught by the no_network guard.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import time
from collections.abc import Callable
from typing import Any

import litellm
from litellm import exceptions as llm_exc

from mastrace.core.errors import ConfigError
from mastrace.core.logging import get_logger
from mastrace.core.schemas import ModelRequest, ModelResponse
from mastrace.settings import ModelConfig

log = get_logger("providers.litellm")

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    llm_exc.APIConnectionError,
    llm_exc.Timeout,
    llm_exc.RateLimitError,
    llm_exc.ServiceUnavailableError,
    llm_exc.InternalServerError,
    llm_exc.BadGatewayError,
)


class LiteLLMProvider:
    """Calls `litellm.completion` at the request's temperature (always 0 in this testbed)."""

    name = "litellm"

    def __init__(
        self,
        cfg: ModelConfig,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        completion: Callable[..., Any] | None = None,
    ) -> None:
        if cfg.provider != "litellm" or not cfg.model:
            raise ConfigError(f"model key {cfg.key!r} is not a configured litellm model")
        self.cfg = cfg
        extras = ",".join(f"{k}={v}" for k, v in sorted(cfg.extra_params.items()))
        self.identity = cfg.model + (f"[{extras}]" if extras else "")
        self.max_retries = max_retries
        self._sleep = sleep
        self._completion = completion or litellm.completion

    def _kwargs(self, request: ModelRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if self.cfg.seed_supported and request.seed is not None:
            kwargs["seed"] = request.seed
        kwargs.update(self.cfg.extra_params)
        base = self.cfg.api_base()
        if base:
            kwargs["api_base"] = base
        return kwargs

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Call the model, retrying transient errors up to `max_retries` times."""
        kwargs = self._kwargs(request)
        attempt = 0
        while True:
            try:
                resp = self._completion(**kwargs)
                break
            except TRANSIENT_ERRORS as e:
                if attempt >= self.max_retries:
                    raise
                attempt += 1
                log.warning(
                    "transient error from %s (retry %d/%d): %s",
                    self.cfg.model,
                    attempt,
                    self.max_retries,
                    type(e).__name__,
                )
                self._sleep(2.0 ** (attempt - 1))
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return ModelResponse(
            text=text,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
