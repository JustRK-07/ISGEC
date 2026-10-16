"""SHA-256 hashing helper."""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of `data`."""
    return hashlib.sha256(data).hexdigest()
