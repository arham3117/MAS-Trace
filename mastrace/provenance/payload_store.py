"""Content-addressed payload store: `payloads/<aa>/<sha256 hex>` (plan.md §7.5, P1.3)."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from mastrace.core.canonical import sha256_hex
from mastrace.core.errors import InvalidPayloadRef, PayloadMissing

_REF = re.compile(r"sha256:([0-9a-f]{64})")


def parse_ref(ref: str) -> str:
    """Return the hex digest of a `sha256:<hex>` reference."""
    m = _REF.fullmatch(ref)
    if m is None:
        raise InvalidPayloadRef(f"not a payload ref: {ref!r}")
    return m.group(1)


class PayloadStore:
    """Stores UTF-8 text by its SHA-256. Writes are atomic and idempotent."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, ref: str) -> Path:
        """Filesystem path of a reference (the file may not exist)."""
        hexd = parse_ref(ref)
        return self.root / hexd[:2] / hexd

    def put(self, text: str) -> str:
        """Store `text` and return its reference. Storing the same text twice writes one file."""
        data = text.encode("utf-8")
        ref = f"sha256:{sha256_hex(data)}"
        path = self.path_for(ref)
        if path.exists():
            return ref
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return ref

    def get(self, ref: str) -> str:
        """Return the stored text, raising `PayloadMissing` if it is absent."""
        path = self.path_for(ref)
        try:
            return path.read_bytes().decode("utf-8")
        except FileNotFoundError as e:
            raise PayloadMissing(ref) from e

    def exists(self, ref: str) -> bool:
        """True if a file exists for this reference."""
        return self.path_for(ref).is_file()

    def verify(self, ref: str) -> bool:
        """True if the file exists and its content hashes to the reference."""
        path = self.path_for(ref)
        if not path.is_file():
            return False
        return sha256_hex(path.read_bytes()) == parse_ref(ref)
