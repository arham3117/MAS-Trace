"""Canonical JSON and the hashes built on it (plan.md §7.6, §7.7)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


def canonical_json(obj: Any) -> str:
    """Serialize with sorted keys, no whitespace, and unicode kept as-is."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str | bytes) -> str:
    """SHA-256 hex digest; text is encoded as UTF-8."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def request_hash_model(
    model: str,
    messages: Sequence[Mapping[str, Any]],
    temperature: float,
    max_tokens: int,
    seed: int | None,
) -> str:
    """Cache key of a model call: hash of model name, full message list and sampling params."""
    return sha256_hex(
        canonical_json(
            {
                "model": model,
                "messages": [dict(m) for m in messages],
                "params": {"temperature": temperature, "max_tokens": max_tokens, "seed": seed},
            }
        )
    )


def request_hash_tool(tool: str, args: Mapping[str, Any], env_snapshot_hash: str) -> str:
    """Cache key of a tool call: hash of tool name, arguments and the environment snapshot."""
    return sha256_hex(canonical_json({"tool": tool, "args": dict(args), "env": env_snapshot_hash}))
