"""Local rotating debug log — never stores private keys."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class DebugLog:
    def __init__(self, path: Path, max_bytes: int = 200_000):
        self.path = Path(path)
        self.max_bytes = max_bytes
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def write(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        line = ts + "Z  " + msg + "\n"
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
            if self.path.stat().st_size > self.max_bytes:
                text = self.path.read_text(encoding="utf-8")
                self.path.write_text(text[-(self.max_bytes // 2):], encoding="utf-8")
        except Exception:
            pass

    def read_tail(self, max_chars: int = 12_000) -> str:
        try:
            if not self.path.exists():
                return "(empty log)"
            text = self.path.read_text(encoding="utf-8")
            if len(text) > max_chars:
                return "...\n" + text[-max_chars:]
            return text or "(empty log)"
        except Exception as e:
            return "(could not read log: %s)" % e

    def clear(self) -> None:
        try:
            self.path.write_text("", encoding="utf-8")
        except Exception:
            pass
