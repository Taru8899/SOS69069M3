"""Sign plain ≤64-char metadata for SOS 69069.

intended_to=None  → self-post (MIND)
intended_to=addr  → directed post (CHAT / BOARD)
"""

from typing import Optional, Tuple

from .config import MAX_METADATA_LENGTH
from .crypto_utils import random_payload_hash
from .eip712 import sign_record
from .ethcrypto import KeyPair, normalize_address


def prepare_and_sign(
    key: KeyPair,
    plaintext: str,
    intended_to: Optional[str] = None,
    reply_code: str = "",
) -> Tuple[bytes, str, bytes]:
    """
    Returns (payload_hash, metadata, signature).
    If intended_to is None, posts to self (MIND).
    """
    text = plaintext.strip()
    code = (reply_code or "").strip().lstrip("#")
    if code:
        metadata = f"#{code[:4].upper()} " + text
    else:
        metadata = text

    if len(metadata.encode("utf-8")) > MAX_METADATA_LENGTH:
        raise ValueError(f"Message limited to {MAX_METADATA_LENGTH} characters")

    target = normalize_address(intended_to) if intended_to else key.address
    payload_hash = random_payload_hash()
    signature = sign_record(key, target, payload_hash, metadata)
    return payload_hash, metadata, signature


def short_code(payload_hash_hex: str) -> str:
    h = str(payload_hash_hex).removeprefix("0x")
    return h[:4].upper()
