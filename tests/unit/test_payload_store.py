"""P1.3: PayloadStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from mastrace.core.errors import InvalidPayloadRef, PayloadMissing
from mastrace.provenance.payload_store import PayloadStore


@pytest.fixture
def store(tmp_path: Path) -> PayloadStore:
    return PayloadStore(tmp_path / "payloads")


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def test_put_get_round_trip(store: PayloadStore) -> None:
    ref = store.put("héllo ✓")
    assert ref.startswith("sha256:") and len(ref) == 7 + 64
    assert store.get(ref) == "héllo ✓"
    hexd = ref.removeprefix("sha256:")
    assert store.path_for(ref) == store.root / hexd[:2] / hexd


def test_same_text_twice_creates_one_file(store: PayloadStore) -> None:
    assert store.put("same") == store.put("same")
    assert len(_files(store.root)) == 1


def test_no_temp_files_left(store: PayloadStore) -> None:
    store.put("a")
    store.put("b")
    assert not [p for p in _files(store.root) if p.name.startswith(".tmp-")]


def test_corrupted_file_detected(store: PayloadStore) -> None:
    ref = store.put("original")
    assert store.verify(ref)
    store.path_for(ref).write_text("tampered")
    assert not store.verify(ref)


def test_missing_ref_raises(store: PayloadStore) -> None:
    ref = "sha256:" + "0" * 64
    with pytest.raises(PayloadMissing):
        store.get(ref)
    assert not store.verify(ref)
    assert not store.exists(ref)


def test_invalid_ref(store: PayloadStore) -> None:
    with pytest.raises(InvalidPayloadRef):
        store.get("md5:abc")
    with pytest.raises(InvalidPayloadRef):
        store.get("sha256:../../etc/passwd")
