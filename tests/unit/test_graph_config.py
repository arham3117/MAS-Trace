"""P3.1: graph configs load and validate; each stage rule has a negative test."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from mastrace.core.errors import ConfigError
from mastrace.runtime.graph_config import (
    GRAPHS_DIR,
    all_graph_names,
    config_hash,
    load_graph,
)

ALL = [
    "s1_chain",
    "s1_fanin",
    "s1_fanout",
    "s2_two_way_chain",
    "s2_two_way_mesh",
    "s3_mixed_two_paths",
    "s3_whiteboard",
]


def test_all_seven_configs_present() -> None:
    assert all_graph_names() == ALL


@pytest.mark.parametrize("name", ALL)
def test_config_loads(name: str) -> None:
    cfg = load_graph(name)
    assert cfg.name == name
    assert cfg.stage == int(name[1])
    assert len(cfg.agents) == 5


def test_shapes() -> None:
    fanin = load_graph("s1_fanin")
    assert fanin.entry_agents == ["A", "B"]
    assert [a.role for a in fanin.agents][:2] == ["researcher", "researcher_2"]
    fanout = load_graph("s1_fanout")
    assert fanout.out_neighbours("D") == []
    assert fanout.out_neighbours("A") == ["B", "C"]
    mixed = load_graph("s3_mixed_two_paths")
    assert mixed.out_neighbours("B") == ["A", "C", "D"]
    assert mixed.link_type("D", "E") == "two_way"
    for name in ALL:
        cfg = load_graph(name)
        sink = cfg.agent(cfg.sink_agent)
        assert sink.role == "operator" and "send_email" in sink.tools
        assert sum("send_email" in a.tools for a in cfg.agents) == 1


def test_hash_stable_and_sensitive() -> None:
    assert config_hash(load_graph("s1_chain")) == config_hash(load_graph("s1_chain"))
    assert config_hash(load_graph("s1_chain")) != config_hash(load_graph("s1_fanout"))


def test_load_by_path() -> None:
    assert load_graph(GRAPHS_DIR / "s1_chain.yaml").name == "s1_chain"


def test_unknown_config() -> None:
    with pytest.raises(ConfigError):
        load_graph("nope")


def _variant(tmp_path: Path, base: str, **changes: object) -> Path:
    d = yaml.safe_load((GRAPHS_DIR / f"{base}.yaml").read_text())
    d.update(changes)
    p = tmp_path / "variant.yaml"
    p.write_text(yaml.safe_dump(d))
    return p


def test_stage1_negative(tmp_path: Path) -> None:
    links = [
        {"from": "A", "to": "B", "type": "two_way"},
        {"from": "B", "to": "C", "type": "one_way"},
        {"from": "C", "to": "D", "type": "one_way"},
        {"from": "D", "to": "E", "type": "one_way"},
    ]
    with pytest.raises(ValidationError, match="rule 4"):
        load_graph(_variant(tmp_path, "s1_chain", links=links))


def test_stage2_negative(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="rule 5"):
        load_graph(_variant(tmp_path, "s1_chain", stage=2))


def test_stage3_negative(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="rule 6"):
        load_graph(_variant(tmp_path, "s2_two_way_chain", stage=3))


def test_rule7_unknown_role(tmp_path: Path) -> None:
    d = yaml.safe_load((GRAPHS_DIR / "s1_chain.yaml").read_text())
    d["agents"][1]["role"] = "astrologer"
    with pytest.raises(ValueError, match="rule 7"):
        load_graph(_variant(tmp_path, "s1_chain", agents=d["agents"]))


def test_rule7_unknown_tool(tmp_path: Path) -> None:
    d = yaml.safe_load((GRAPHS_DIR / "s1_chain.yaml").read_text())
    d["agents"][0]["tools"] = ["web_fetch", "shell"]
    with pytest.raises(ValueError, match="rule 7: unknown tool 'shell'"):
        load_graph(_variant(tmp_path, "s1_chain", agents=d["agents"]))
