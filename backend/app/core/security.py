from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone


def generate_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def generate_uuid() -> str:
    return uuid.uuid4().hex


def file_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
