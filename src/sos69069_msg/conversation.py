"""Local state for SOS69069 M3.

MIND bind  — session only (cleared on every app start)
CHAT target — durable across restarts
BOARD list  — durable in settings (handled in app settings.json)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ethcrypto import KeyPair, normalize_address


def random_wallet() -> KeyPair:
    return KeyPair.from_private_key(os.urandom(32))


@dataclass
class WalletStore:
    """Durable conversation wallet (signing key)."""
    path: Path

    def load(self) -> Optional[KeyPair]:
        if not self.path.exists():
            return None
        try:
            j = json.loads(self.path.read_text())
            key = bytes.fromhex(str(j["key"]).removeprefix("0x"))
            return KeyPair.from_private_key(key)
        except Exception:
            return None

    def save(self, kp: KeyPair) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "address": kp.address,
            "key": kp.private_key.hex(),
        }))
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass


@dataclass
class ChatTargetStore:
    """Durable CHAT target address — survives app restart."""
    path: Path

    def load(self) -> Optional[str]:
        if not self.path.exists():
            return None
        try:
            j = json.loads(self.path.read_text())
            return normalize_address(j["target"])
        except Exception:
            return None

    def save(self, target: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"target": normalize_address(target)}))

    def clear(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass


@dataclass
class MindBind:
    """Session-only Other address for MIND. Never durable."""
    other: Optional[str] = None

    def set(self, other: str) -> None:
        self.other = normalize_address(other)

    def clear(self) -> None:
        self.other = None
