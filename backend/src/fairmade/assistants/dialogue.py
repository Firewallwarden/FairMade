"""Prior dialogue supplies intent, never authoritative facts or current permissions."""

import hashlib
import re
from dataclasses import dataclass, field
from decimal import Decimal

from fairmade.assistants.context import QUESTION_AMOUNTS
from fairmade.assistants.schemas import Evidence
from fairmade.assistants.serialization import encoded

SCENARIO_TITLE = "Deterministic requested price scenarios"
FOLLOW_UP = re.compile(
    r"\b(that|those|previous|earlier|same|it|they|why|explain further|tell me more)\b",
    re.IGNORECASE,
)
MAX_CONTEXT_BYTES = 12000
MAX_CONTEXT_TURNS = 6


def evidence_digest(facts: list[Evidence]) -> str:
    return hashlib.sha256(encoded(facts).encode("utf-8")).hexdigest()


def source_digest(facts: list[Evidence]) -> str:
    # Saved answers remain readable while their original business sources match.
    # Prompt replay uses the full digest, including this turn's chosen scenarios.
    return evidence_digest([fact for fact in facts if fact.title != SCENARIO_TITLE])


@dataclass(frozen=True)
class PriorTurn:
    question: str
    paragraphs: tuple[str, ...]
    evidence_hash: str


@dataclass
class Dialogue:
    turns: list[PriorTurn] = field(default_factory=list)
    previous_prices: list[Decimal] = field(default_factory=list)
    previous_price_basis: dict[str, str] | None = None
    context_turns: int = 0

    def messages(self, facts: list[Evidence]) -> list[dict[str, str]]:
        current_hash = evidence_digest(facts)
        selected = []
        size = 0
        for turn in reversed(self.turns[-MAX_CONTEXT_TURNS:]):
            pair = [
                {
                    "role": "user",
                    "content": QUESTION_AMOUNTS.sub("[prior proposed value]", turn.question),
                }
            ]
            # Never replay explanations grounded in changed/withdrawn disclosures.
            if turn.evidence_hash == current_hash:
                pair.append(
                    {
                        "role": "assistant",
                        "content": QUESTION_AMOUNTS.sub("[prior value]", " ".join(turn.paragraphs)),
                    }
                )
            pair_size = sum(len(row["content"].encode("utf-8")) for row in pair)
            if size + pair_size > MAX_CONTEXT_BYTES:
                break
            selected.append(pair)
            size += pair_size
        self.context_turns = len(selected)
        return [message for pair in reversed(selected) for message in pair]
