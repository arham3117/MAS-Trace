"""P1.2: canonical JSON and hashing."""

from __future__ import annotations

import hashlib
import json

from mastrace.core.canonical import (
    canonical_json,
    request_hash_model,
    request_hash_tool,
    sha256_hex,
)


def test_canonical_json_format() -> None:
    assert canonical_json({"b": 1, "a": [1, {"d": 2, "c": 3}]}) == '{"a":[1,{"c":3,"d":2}],"b":1}'


def test_canonical_json_insertion_order_independent() -> None:
    a = {"x": 1, "y": {"p": 1, "q": 2}}
    b = {"y": {"q": 2, "p": 1}, "x": 1}
    assert canonical_json(a) == canonical_json(b)


def test_unicode_preserved() -> None:
    s = canonical_json({"t": "héllo — ✓ 日本"})
    assert "héllo — ✓ 日本" in s
    assert json.loads(s)["t"] == "héllo — ✓ 日本"


def test_sha256_hex_str_and_bytes() -> None:
    assert sha256_hex("abc") == hashlib.sha256(b"abc").hexdigest()
    assert sha256_hex(b"abc") == sha256_hex("abc")
    assert sha256_hex("é") == hashlib.sha256("é".encode()).hexdigest()


MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "héllo"}]


def test_request_hash_model_matches_spec() -> None:
    expected = sha256_hex(
        canonical_json(
            {
                "model": "m",
                "messages": MSGS,
                "params": {"temperature": 0, "max_tokens": 100, "seed": 7},
            }
        )
    )
    assert request_hash_model("m", MSGS, 0, 100, 7) == expected


def test_request_hash_model_stable_across_key_order() -> None:
    reordered = [{"content": m["content"], "role": m["role"]} for m in MSGS]
    assert request_hash_model("m", MSGS, 0, 100, 7) == request_hash_model("m", reordered, 0, 100, 7)


def test_request_hash_model_sensitive() -> None:
    base = request_hash_model("m", MSGS, 0, 100, 7)
    assert request_hash_model("m2", MSGS, 0, 100, 7) != base
    assert request_hash_model("m", MSGS[:1], 0, 100, 7) != base
    assert request_hash_model("m", MSGS, 0, 100, 8) != base
    assert request_hash_model("m", MSGS, 0, 101, 7) != base


def test_request_hash_tool() -> None:
    h1 = request_hash_tool("web_fetch", {"url": "u", "x": 1}, "env1")
    h2 = request_hash_tool("web_fetch", {"x": 1, "url": "u"}, "env1")
    assert h1 == h2
    assert request_hash_tool("web_fetch", {"url": "u", "x": 1}, "env2") != h1
    expected = sha256_hex(
        canonical_json({"tool": "web_fetch", "args": {"url": "u", "x": 1}, "env": "env1"})
    )
    assert h1 == expected
