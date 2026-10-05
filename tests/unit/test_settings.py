"""P0.3: settings and model config."""

from pathlib import Path

import pytest

from mastrace.core.errors import UnknownModelKey
from mastrace.settings import Settings, allowed_model_hosts, load_model, load_models

EXPECTED_KEYS = ["commercial", "dev_open", "scripted_gullible", "scripted_resistant"]


def test_all_keys_present() -> None:
    assert sorted(load_models()) == EXPECTED_KEYS


@pytest.mark.parametrize("key", EXPECTED_KEYS)
def test_load_each_key(key: str) -> None:
    cfg = load_model(key)
    assert cfg.key == key
    assert cfg.temperature == 0


def test_scripted_keys() -> None:
    assert load_model("scripted_gullible").policy == "gullible"
    assert load_model("scripted_resistant").policy == "resistant"


def test_dev_open_is_litellm() -> None:
    cfg = load_model("dev_open")
    assert cfg.provider == "litellm"
    assert cfg.model
    assert cfg.api_base_env == "OLLAMA_BASE_URL"
    assert cfg.configured


def test_commercial_is_placeholder() -> None:
    assert not load_model("commercial").configured


def test_unknown_key_raises_clear_error() -> None:
    with pytest.raises(UnknownModelKey, match=r"unknown model key 'nope'.*dev_open"):
        load_model("nope")


def test_api_base_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://model-host.test:11434")
    assert load_model("dev_open").api_base() == "http://model-host.test:11434"
    assert "model-host.test" in allowed_model_hosts()


def test_bad_models_file(tmp_path: Path) -> None:
    bad = tmp_path / "models.yaml"
    bad.write_text("models:\n  x: {provider: scripted}\n")
    with pytest.raises(ValueError, match="needs a policy"):
        load_models(bad)


def test_settings_derive_paths(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path)
    assert s.cache_path == tmp_path / "cache" / "model_cache.sqlite"
    assert s.keys_dir == tmp_path / "keys"
    assert s.ground_truth_path == tmp_path / "ground_truth.sqlite"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MASTRACE_DATA_DIR", str(tmp_path))
    assert Settings().data_dir == tmp_path
