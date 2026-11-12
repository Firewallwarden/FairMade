"""Erase profile-derived answer copies without deleting the user's own messages."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fairmade.models import AssistantConversation, AssistantTurn
from fairmade.personalization.constants import TITLE


def erase_answers(db: Session, account_id: str) -> None:
    rows = db.scalars(
        select(AssistantTurn)
        .join(AssistantConversation, AssistantConversation.id == AssistantTurn.conversation_id)
        .where(
            AssistantConversation.account_id == account_id,
            AssistantConversation.role == "buyer",
        )
    ).all()
    for row in rows:
        if not any(fact["title"] == TITLE for fact in row.response["evidence"]):
            continue
        row.response = {
            "assistant_version": "fairmade-assistant-v1",
            "role": "buyer",
            "provider": "ollama_local",
            "model": "qwen3:8b",
            "generated_at": row.response["generated_at"],
            "facts": [],
            "paragraphs": [],
            "evidence": [],
            "notices": ["Profile-derived answer erased; your original question is retained."],
        }
        row.source_hash = "0" * 64
