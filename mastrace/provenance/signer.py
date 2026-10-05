"""Ed25519 signing of event record hashes (plan.md §7.6, P1.4).

The signature covers the 32 raw bytes of the record hash (`bytes.fromhex(record_hash)`).
The private key (32-byte seed, hex) is `recorder_ed25519.key`, mode 0600; the public key
(base64) is written next to it as `recorder_ed25519.pub` so the verifier never loads the
private key.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

KEY_FILE = "recorder_ed25519.key"
PUB_FILE = "recorder_ed25519.pub"


class Signer:
    """Loads (or creates on first use) the recorder's Ed25519 key."""

    def __init__(self, keys_dir: Path) -> None:
        self.keys_dir = keys_dir
        self._key = self._load_or_create()

    def _load_or_create(self) -> SigningKey:
        path = self.keys_dir / KEY_FILE
        if path.exists():
            return SigningKey(bytes.fromhex(path.read_text(encoding="ascii").strip()))
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        key = SigningKey.generate()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as f:
            f.write(bytes(key).hex())
        os.chmod(path, 0o600)  # umask may have narrowed or widened the create mode
        (self.keys_dir / PUB_FILE).write_text(
            base64.b64encode(bytes(key.verify_key)).decode("ascii"), encoding="ascii"
        )
        return key

    @property
    def public_key(self) -> str:
        """Base64-encoded Ed25519 public key."""
        return base64.b64encode(bytes(self._key.verify_key)).decode("ascii")

    def sign(self, record_hash: str) -> str:
        """Sign a hex record hash and return the base64 signature."""
        sig = self._key.sign(bytes.fromhex(record_hash)).signature
        return base64.b64encode(sig).decode("ascii")


def load_public_key(keys_dir: Path) -> str:
    """Read the base64 public key written by `Signer`."""
    return (keys_dir / PUB_FILE).read_text(encoding="ascii").strip()


def verify(record_hash: str, sig: str, pubkey: str) -> bool:
    """True if `sig` (base64) is a valid signature of `record_hash` (hex) under `pubkey`."""
    try:
        VerifyKey(base64.b64decode(pubkey)).verify(
            bytes.fromhex(record_hash), base64.b64decode(sig)
        )
    except (BadSignatureError, ValueError, TypeError):
        return False
    return True
