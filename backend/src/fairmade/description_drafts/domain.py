"""Canonical content/source digests; no HTTP, storage or model dependency."""

import hashlib
import json


def digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def preview_digest(identifier, revision: int, description: str, source_hash: str) -> str:
    return digest(
        {
            "draft_id": str(identifier),
            "revision": revision,
            "description": description,
            "source_hash": source_hash,
        }
    )
