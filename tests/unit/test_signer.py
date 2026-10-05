"""P1.4: Signer."""

from __future__ import annotations

import stat
from pathlib import Path

from mastrace.core.canonical import sha256_hex
from mastrace.provenance.signer import KEY_FILE, Signer, load_public_key, verify

H = sha256_hex("record")


def test_sign_and_verify(tmp_path: Path) -> None:
    s = Signer(tmp_path)
    assert verify(H, s.sign(H), s.public_key)


def test_key_file_mode_0600(tmp_path: Path) -> None:
    Signer(tmp_path / "keys")
    mode = stat.S_IMODE((tmp_path / "keys" / KEY_FILE).stat().st_mode)
    assert mode == 0o600


def test_key_is_reused(tmp_path: Path) -> None:
    a, b = Signer(tmp_path), Signer(tmp_path)
    assert a.public_key == b.public_key
    assert load_public_key(tmp_path) == a.public_key
    assert verify(H, a.sign(H), b.public_key)


def test_different_key_fails(tmp_path: Path) -> None:
    a = Signer(tmp_path / "a")
    b = Signer(tmp_path / "b")
    assert not verify(H, b.sign(H), a.public_key)


def test_wrong_hash_fails(tmp_path: Path) -> None:
    s = Signer(tmp_path)
    assert not verify(sha256_hex("other"), s.sign(H), s.public_key)


def test_garbage_signature_fails(tmp_path: Path) -> None:
    s = Signer(tmp_path)
    assert not verify(H, "not-base64!!", s.public_key)
    assert not verify(H, "AAAA", s.public_key)
