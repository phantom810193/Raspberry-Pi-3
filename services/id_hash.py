"""Utility helpers for generating anonymised member identifiers."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Iterable

def stable_id(embedding: Iterable[float], salt: str) -> str:
    """Return a deterministic HMAC digest for the given face embedding."""
    payload = json.dumps(list(embedding), separators=(",", ":"))
    mac = hmac.new(salt.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()
