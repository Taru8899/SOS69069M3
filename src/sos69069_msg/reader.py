"""Ledger readers for SOS69069 M3.

MIND  — self-posts for My (+ optional Other), time merge
CHAT / BOARD — all SignatureRecorded with intendedTo = target
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from .abi import SIGNATURE_RECORDED_TOPIC, decode_signature_recorded
from .config import CONTRACT_ADDRESS
from .ethcrypto import normalize_address, parse_address
from .message_engine import short_code
from .rpc import RpcError

OVERLAP = 20
DEFAULT_LOOKBACK = 500_000
MIN_CHUNK = 1_000
MAX_MESSAGES = 50
PAGE_SIZE = 10
_RANGE_HINTS = ("range", "limit", "exceed", "too many", "too large", "large", "max",
                "results", "10000", "query returned", "more than")


def _addr_from_topic(topic: str) -> str:
    return normalize_address("0x" + topic[-40:])


def _is_range_error(err: Exception) -> bool:
    m = str(err).lower()
    return any(h in m for h in _RANGE_HINTS)


@dataclass
class Message:
    block: int
    log_index: int
    tx_hash: str
    timestamp: int
    signer: str
    submitter: str
    text: str
    payload_hash: str = ""
    intended_to: str = ""

    def who_label(self, my_address: str = "") -> str:
        if my_address and self.signer.lower() == my_address.lower():
            return "Me"
        return self.signer


def scan_intended_to(
    rpc,
    intended_to: str,
    from_block: int,
    to_block: int,
    chunk: Optional[int] = None,
    progress: Optional[Callable[[str], None]] = None,
    self_only: bool = False,
) -> List[Message]:
    """All SignatureRecorded where intendedTo == intended_to.
    If self_only, keep only signer == intendedTo (MIND).
    """
    d_topic = "0x" + parse_address(intended_to).rjust(32, b"\x00").hex()
    contract = normalize_address(CONTRACT_ADDRESS)
    topic0 = "0x" + SIGNATURE_RECORDED_TOPIC.hex()
    chunk = chunk or max(1, to_block - from_block + 1)
    msgs: List[Message] = []
    start = from_block
    target_l = normalize_address(intended_to).lower()
    while start <= to_block:
        end = min(start + chunk - 1, to_block)
        if progress:
            progress(f"Scanning {intended_to[:10]}… {start}–{end}")
        try:
            logs = rpc.get_logs({
                "address": contract,
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "topics": [topic0, None, d_topic],
            })
        except RpcError as e:
            if not _is_range_error(e):
                raise
            if chunk <= MIN_CHUNK:
                raise RpcError(
                    f"{e}. Range limit — set a later scan-from block."
                ) from e
            chunk = max(MIN_CHUNK, chunk // 2)
            continue

        for log in logs:
            try:
                raw = log.get("data", "")
                if isinstance(raw, str):
                    raw = bytes.fromhex(raw.removeprefix("0x"))
                ph_b, _sig, ts, meta = decode_signature_recorded(raw)
                if not ts and log.get("timeStamp"):
                    ts_raw = log["timeStamp"]
                    ts = int(str(ts_raw), 16) if str(ts_raw).startswith("0x") else int(ts_raw)
                topics = log.get("topics", [])
                signer = _addr_from_topic(topics[1]) if len(topics) > 1 else ""
                submitter = _addr_from_topic(topics[3]) if len(topics) > 3 else ""
                if self_only and signer.lower() != target_l:
                    continue
                msgs.append(Message(
                    block=int(log.get("blockNumber", "0x0"), 16),
                    log_index=int(log.get("logIndex", "0x0"), 16),
                    tx_hash=log.get("transactionHash", ""),
                    timestamp=ts or 0,
                    signer=signer,
                    submitter=submitter,
                    text=meta,
                    payload_hash="0x" + ph_b.hex(),
                    intended_to=normalize_address(intended_to),
                ))
            except Exception:
                continue
        start = end + 1
    return msgs


@dataclass
class Inbox:
    VERSION = 4
    path: str = ""
    last_block: Optional[int] = None
    messages: List[Message] = field(default_factory=list)
    outbox: List[dict] = field(default_factory=list)

    def __init__(self, path: str):
        self.path = path
        self.last_block = None
        self.messages = []
        self.outbox = []
        if os.path.exists(path):
            try:
                with open(path) as f:
                    j = json.load(f)
                self.last_block = j.get("last_block")
                self.outbox = j.get("outbox", [])
                for m in j.get("messages", []):
                    self.messages.append(Message(**m))
            except Exception:
                pass

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump({
                "v": self.VERSION,
                "last_block": self.last_block,
                "messages": [asdict(m) for m in self.messages],
                "outbox": self.outbox,
            }, f)

    def clear(self) -> None:
        self.messages = []
        self.outbox = []
        self.last_block = None
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
        except OSError:
            pass

    def merge(self, new_msgs: List[Message], latest_block: int) -> int:
        existing = {(m.block, m.log_index, m.signer.lower()) for m in self.messages}
        added = 0
        for m in new_msgs:
            key = (m.block, m.log_index, m.signer.lower())
            if key not in existing:
                self.messages.append(m)
                existing.add(key)
                added += 1
        self.messages.sort(key=lambda m: (m.block, m.log_index, m.timestamp))
        if len(self.messages) > MAX_MESSAGES:
            self.messages = self.messages[-MAX_MESSAGES:]
        self.last_block = latest_block
        self._save()
        return added

    def add_pending(self, payload_hash_hex: str, text: str) -> None:
        self.outbox.append({
            "ph": payload_hash_hex, "text": text,
            "ts": int(time.time()), "tx": "",
        })
        self._save()

    def mark_submitted(self, payload_hash_hex: str, tx: str) -> None:
        ph = payload_hash_hex if str(payload_hash_hex).startswith("0x") else ("0x" + str(payload_hash_hex))
        for o in self.outbox:
            op = o["ph"] if str(o["ph"]).startswith("0x") else ("0x" + str(o["ph"]))
            if op.lower() == ph.lower():
                o["tx"] = tx
        self._save()

    def pending(self) -> List[dict]:
        on_chain = {m.payload_hash.lower() for m in self.messages}
        out = []
        for o in self.outbox:
            op = o["ph"] if str(o["ph"]).startswith("0x") else ("0x" + str(o["ph"]))
            if op.lower() not in on_chain and not o.get("tx"):
                out.append(o)
        return out

    def entries(self, my_address: str = "", label_me: bool = True) -> List[dict]:
        """Newest-first structured cards."""
        rows = []
        for o in reversed(self.pending()):
            rows.append({
                "text": o["text"], "who": "Me" if label_me else "",
                "address": "", "tx": "", "block": "", "when": "",
                "code": short_code(o["ph"]), "pending": True,
                "reply_id": short_code(o["ph"]).lower(),
            })
        for m in reversed(self.messages):
            t = datetime.fromtimestamp(m.timestamp, timezone.utc) if m.timestamp else None
            when = t.strftime("%d/%m/%Y, %H:%M:%S") if t else ""
            tx = m.tx_hash if str(m.tx_hash).startswith("0x") else ("0x" + str(m.tx_hash))
            reply_id = tx[2:10] if len(tx) >= 10 else short_code(m.payload_hash).lower()
            who = m.who_label(my_address) if label_me else m.signer
            rows.append({
                "text": m.text, "who": who, "address": m.signer,
                "tx": tx, "block": m.block, "when": when,
                "code": short_code(m.payload_hash), "pending": False,
                "reply_id": reply_id,
            })
        return rows

    def page_count(self) -> int:
        total = len(self.messages) + len(self.pending())
        return max(1, -(-total // PAGE_SIZE))


def _scan_range(rpc, inbox: Inbox, from_block: Optional[int]):
    latest = rpc.block_number()
    if from_block is not None:
        start = from_block
    elif inbox.last_block is not None:
        start = max(0, inbox.last_block + 1 - OVERLAP)
    else:
        start = max(0, latest - DEFAULT_LOOKBACK)
    return start, latest


def sync_mind(
    rpc, my_address: str, other: Optional[str], inbox: Inbox,
    from_block: Optional[int] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> int:
    """Self-posts for My and optional Other, merged by time."""
    start, latest = _scan_range(rpc, inbox, from_block)
    a = normalize_address(my_address)
    msgs = scan_intended_to(rpc, a, start, latest, progress=progress, self_only=True)
    if other:
        b = normalize_address(other)
        msgs += scan_intended_to(rpc, b, start, latest, progress=progress, self_only=True)
    return inbox.merge(msgs, latest)


def sync_to_address(
    rpc, target: str, inbox: Inbox,
    from_block: Optional[int] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> int:
    """All posts with intendedTo = target (CHAT / BOARD)."""
    start, latest = _scan_range(rpc, inbox, from_block)
    t = normalize_address(target)
    msgs = scan_intended_to(rpc, t, start, latest, progress=progress, self_only=False)
    return inbox.merge(msgs, latest)


def count_to_address(rpc, target: str, lookback: int = 200_000) -> int:
    """Approximate message count for ranking boards."""
    latest = rpc.block_number()
    start = max(0, latest - lookback)
    msgs = scan_intended_to(rpc, normalize_address(target), start, latest, self_only=False)
    return len(msgs)
