"""Model providers and a factory keyed by `configs/models.yaml`."""

from __future__ import annotations

from mastrace.core.errors import ConfigError
from mastrace.mediation.providers.base import ModelProvider
from mastrace.mediation.providers.scripted import Policy, ScriptedProvider
from mastrace.settings import ModelConfig


def make_provider(
    cfg: ModelConfig,
    policy_overrides: dict[str, Policy] | None = None,
    feedback_rounds: int = 1,
) -> ModelProvider:
    """Build the provider for a model config. Scripted options are ignored for real models."""
    if cfg.provider == "scripted":
        assert cfg.policy is not None
        return ScriptedProvider(
            cfg.policy, policy_overrides=policy_overrides, feedback_rounds=feedback_rounds
        )
    if not cfg.configured:
        raise ConfigError(f"model key {cfg.key!r} has no model configured yet")
    from mastrace.mediation.providers.litellm_provider import LiteLLMProvider

    return LiteLLMProvider(cfg)


__all__ = ["ModelProvider", "ScriptedProvider", "make_provider"]
