"""Bound evidence before inference, storage, or hashing."""

import json

from fairmade.auth import api_error

MAX_EVIDENCE_BYTES = 24000


def encoded(facts) -> str:
    text = json.dumps([fact.model_dump(mode="json") for fact in facts], ensure_ascii=False)
    if len(text.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise api_error(409, "ASSISTANT_SCOPE_TOO_LARGE", "Select less evidence for this question.")
    return text
