"""Runtime settings and model configuration (`configs/models.yaml`)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mastrace.core.errors import ConfigError, UnknownModelKey

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Paths and defaults, overridable with `MASTRACE_*` environment variables or `.env`."""

    model_config = SettingsConfigDict(env_prefix="MASTRACE_", env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    cache_path: Path | None = None
    keys_dir: Path | None = None
    models_config: Path = REPO_ROOT / "configs" / "models.yaml"
    templates_dir: Path = REPO_ROOT / "env" / "templates"
    default_model_key: str = "dev_open"

    @model_validator(mode="after")
    def _derive_paths(self) -> Settings:
        if self.cache_path is None:
            self.cache_path = self.data_dir / "cache" / "model_cache.sqlite"
        if self.keys_dir is None:
            self.keys_dir = self.data_dir / "keys"
        return self

    @property
    def runs_dir(self) -> Path:
        """Directory holding one subdirectory per run."""
        return self.data_dir / "runs"

    @property
    def ground_truth_path(self) -> Path:
        """Path of the ground-truth DB (opened only by the injector and evaluation)."""
        return self.data_dir / "ground_truth.sqlite"


class ModelConfig(BaseModel):
    """One entry of `configs/models.yaml`."""

    model_config = ConfigDict(extra="forbid")

    key: str
    provider: Literal["scripted", "litellm"]
    policy: Literal["gullible", "resistant"] | None = None
    model: str | None = None
    api_base_env: str | None = None
    temperature: float = 0.0
    seed_supported: bool = False
    max_tokens: int = 1024
    extra_params: dict[str, Any] = {}

    @model_validator(mode="after")
    def _check_provider_fields(self) -> ModelConfig:
        if self.provider == "scripted" and self.policy is None:
            raise ValueError(f"{self.key}: scripted provider needs a policy")
        if self.provider == "litellm" and self.policy is not None:
            raise ValueError(f"{self.key}: policy is only valid for the scripted provider")
        return self

    @property
    def configured(self) -> bool:
        """False for placeholders (e.g. `commercial` before the team picks a model)."""
        return self.provider == "scripted" or self.model is not None

    def api_base(self) -> str | None:
        """Resolve the provider base URL from the environment, if this model uses one."""
        if self.api_base_env is None:
            return None
        return os.environ.get(self.api_base_env) or _dotenv_value(self.api_base_env)


def _dotenv_value(name: str) -> str | None:
    """Read one variable from the repo's `.env` file, if present."""
    path = REPO_ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition("=")
        if sep and k.strip() == name:
            return v.strip() or None
    return None


def load_models(path: Path | None = None) -> dict[str, ModelConfig]:
    """Load and validate every model key in `configs/models.yaml`."""
    path = path or get_settings().models_config
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"model config not found: {path}") from e
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        raise ConfigError(f"{path}: expected a top-level 'models' mapping")
    return {
        key: ModelConfig(key=key, **(spec or {})) for key, spec in sorted(raw["models"].items())
    }


def load_model(key: str, path: Path | None = None) -> ModelConfig:
    """Return the config for one model key, raising `UnknownModelKey` if it is not defined."""
    models = load_models(path)
    if key not in models:
        raise UnknownModelKey(key, sorted(models))
    return models[key]


def allowed_model_hosts(path: Path | None = None) -> set[str]:
    """Hostnames of every configured model provider base URL (for the `no_network` fixture)."""
    hosts: set[str] = set()
    for cfg in load_models(path).values():
        base = cfg.api_base()
        if base:
            host = urlparse(base).hostname
            if host:
                hosts.add(host)
    return hosts


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings instance."""
    return Settings()
