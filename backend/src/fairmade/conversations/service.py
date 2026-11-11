"""Persist completed turns atomically; refresh source access for every read and inference."""

import hashlib
import json
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from fairmade.assistants.dialogue import (
    FOLLOW_UP,
    SCENARIO_TITLE,
    Dialogue,
    PriorTurn,
    evidence_digest,
    source_digest,
)
from fairmade.assistants.gateway import Gateway
from fairmade.assistants.history import period_for
from fairmade.assistants.schemas import (
    AssistantResponse,
    BuyerQuestion,
    Evidence,
    HistoryPeriod,
    SellerQuestion,
)
from fairmade.assistants.service import answer, load_evidence
from fairmade.auth import api_error
from fairmade.conversations import repository
from fairmade.conversations.schemas import (
    ConversationResponse,
    CreateConversation,
    CreateTurn,
    TurnResponse,
    question_for,
)
from fairmade.database import utcnow
from fairmade.models import AssistantConversation, AssistantTurn

MAX_RESPONSE_BYTES = 65536


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def metadata(row: AssistantConversation) -> ConversationResponse:
    return ConversationResponse.model_validate(row, from_attributes=True)


def conflict():
    return api_error(
        409, "REVISION_CONFLICT", "Reload the conversation before sending another turn."
    )


def turn_body(
    scope: dict, question: str, history_period: dict | None = None
) -> SellerQuestion | BuyerQuestion:
    body = question_for(scope, question)
    if isinstance(body, SellerQuestion) and history_period is not None:
        body = body.model_copy(
            update={"history_period": HistoryPeriod.model_validate(history_period)}
        )
    return body


def checked_scope(db: Session, account_id: str, session_hash: str, row: AssistantConversation):
    return load_evidence(
        db, account_id, session_hash, question_for(row.scope, "Explain the selected evidence.")
    )


def create(
    db: Session, account_id: str, session_hash: str, body: CreateConversation
) -> ConversationResponse:
    repository.reserve_account(db, account_id)
    repository.purge_expired(db, account_id)
    scope = body.scope.model_dump(mode="json", exclude_none=True)
    existing = db.scalar(
        select(AssistantConversation).where(
            AssistantConversation.account_id == account_id,
            AssistantConversation.request_id == str(body.request_id),
        )
    )
    if existing is not None:
        if existing.scope != scope:
            raise api_error(
                409, "REQUEST_ID_CONFLICT", "Use a new request_id for a different scope."
            )
        checked_scope(db, account_id, session_hash, existing)
        db.commit()
        return metadata(existing)
    count = db.scalar(
        select(func.count())
        .select_from(AssistantConversation)
        .where(AssistantConversation.account_id == account_id)
    )
    if count >= repository.MAX_CONVERSATIONS:
        raise api_error(
            409, "CONVERSATION_LIMIT", "Delete an old conversation before creating one."
        )
    now = utcnow()
    row = AssistantConversation(
        account_id=account_id,
        request_id=str(body.request_id),
        role=scope["role"],
        scope=scope,
        revision=0,
        created_at=now,
        updated_at=now,
        expires_at=repository.expires_after(now),
    )
    checked_scope(db, account_id, session_hash, row)
    db.add(row)
    db.commit()
    return metadata(row)


def list_conversations(db: Session, account_id: str, limit: int, offset: int) -> dict:
    rows = db.scalars(
        select(AssistantConversation)
        .where(
            AssistantConversation.account_id == account_id,
            AssistantConversation.expires_at > utcnow(),
        )
        .order_by(AssistantConversation.updated_at.desc(), AssistantConversation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": [metadata(row) for row in rows], "limit": limit, "offset": offset}


def get(
    db: Session, account_id: str, session_hash: str, conversation_id: str
) -> ConversationResponse:
    row = repository.owned(db, account_id, conversation_id)
    checked_scope(db, account_id, session_hash, row)
    return metadata(row)


def remove(db: Session, account_id: str, conversation_id: str) -> None:
    # Owners can erase even when seller access or the original listing is gone.
    # Expired conversations also remain erasable until physical purging occurs.
    db.execute(
        delete(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.account_id == account_id,
        )
    )
    db.commit()


def view_turn(
    db: Session, account_id: str, session_hash: str, scope: dict, row: AssistantTurn
) -> TurnResponse:
    facts = load_evidence(
        db, account_id, session_hash, turn_body(scope, row.question, row.history_period)
    )
    current = source_digest(facts) == row.source_hash
    return TurnResponse(
        id=row.id,
        conversation_id=row.conversation_id,
        request_id=row.request_id,
        revision=row.revision,
        question=row.question,
        answer=AssistantResponse.model_validate(row.response) if current else None,
        answer_status="available" if current else "evidence_changed",
        context_turns=row.context_turns,
        created_at=row.created_at,
    )


def list_turns(
    db: Session,
    account_id: str,
    session_hash: str,
    conversation_id: str,
    limit: int,
    offset: int,
) -> dict:
    conversation = repository.owned(db, account_id, conversation_id)
    checked_scope(db, account_id, session_hash, conversation)
    rows = db.scalars(
        select(AssistantTurn)
        .where(AssistantTurn.conversation_id == conversation.id)
        .order_by(AssistantTurn.revision)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [view_turn(db, account_id, session_hash, conversation.scope, row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


def retry(
    db: Session,
    account_id: str,
    session_hash: str,
    conversation: AssistantConversation,
    row: AssistantTurn,
    request_hash: str,
) -> TurnResponse:
    if row.request_hash != request_hash:
        raise api_error(
            409, "REQUEST_ID_CONFLICT", "Use a new request_id for a different question."
        )
    return view_turn(db, account_id, session_hash, conversation.scope, row)


def prepare_context(
    rows: list[AssistantTurn], scope: dict, text: str
) -> tuple[SellerQuestion | BuyerQuestion, Dialogue, dict | None]:
    basis = None
    if rows and rows[-1].proposed_prices:
        snapshot = next(
            fact["data"]["product_snapshot"]
            for fact in rows[-1].response["evidence"]
            if fact["title"] == "Selected saved production economics"
        )
        basis = {key: snapshot[key] for key in ("product_type", "selling_unit")}
    dialogue = Dialogue(
        turns=[
            PriorTurn(
                question=row.question,
                paragraphs=tuple(p["text"] for p in row.response["paragraphs"]),
                evidence_hash=evidence_digest(
                    [Evidence.model_validate(fact) for fact in row.response["evidence"]]
                ),
            )
            for row in rows
        ],
        previous_prices=[Decimal(value) for value in rows[-1].proposed_prices] if rows else [],
        previous_price_basis=basis,
    )
    question = question_for(scope, text)
    if isinstance(question, SellerQuestion):
        period = period_for(question)
        if period is None and rows and FOLLOW_UP.search(question.question):
            previous = rows[-1].history_period
            period = HistoryPeriod.model_validate(previous) if previous else None
        if period is not None:
            question = question.model_copy(update={"history_period": period})
    period_json = (
        question.history_period.model_dump(mode="json")
        if isinstance(question, SellerQuestion) and question.history_period is not None
        else None
    )
    return question, dialogue, period_json


def append(
    db: Session,
    account_id: str,
    session_hash: str,
    conversation_id: str,
    body: CreateTurn,
    gateway: Gateway,
) -> TurnResponse:
    conversation = repository.owned(db, account_id, conversation_id)
    scope = dict(conversation.scope)
    request_hash = digest(body.model_dump(mode="json"))
    existing = repository.request_turn(db, conversation_id, str(body.request_id))
    if existing is not None:
        return retry(db, account_id, session_hash, conversation, existing, request_hash)
    if conversation.revision != body.expected_revision:
        raise conflict()
    if conversation.revision >= repository.MAX_TURNS:
        raise api_error(409, "CONVERSATION_FULL", "Start a new conversation for more questions.")
    rows = repository.recent(db, conversation_id)
    question, dialogue, period_json = prepare_context(rows, scope, body.question)
    response = answer(db, account_id, session_hash, question, gateway, dialogue)
    response_json = response.model_dump(mode="json")
    if len(json.dumps(response_json).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise api_error(409, "ASSISTANT_SCOPE_TOO_LARGE", "Select less evidence for this question.")
    response_hash = source_digest(response.evidence)
    # End the inference read transaction before the first write. A conditional
    # update serializes final writes without reserving the DB during GPU work.
    db.rollback()
    if not repository.append_revision(db, account_id, conversation_id, body.expected_revision):
        db.rollback()
        current = repository.owned(db, account_id, conversation_id)
        existing = repository.request_turn(db, conversation_id, str(body.request_id))
        if existing is not None:
            return retry(db, account_id, session_hash, current, existing, request_hash)
        raise conflict()
    fresh = load_evidence(db, account_id, session_hash, question)
    if source_digest(fresh) != response_hash:
        raise api_error(409, "ASSISTANT_EVIDENCE_CHANGED", "Evidence changed; ask again.")
    prices = [
        scenario["price"]
        for fact in response.evidence
        if fact.title == SCENARIO_TITLE
        for scenario in fact.data["scenarios"]
    ]
    row = AssistantTurn(
        conversation_id=conversation_id,
        request_id=str(body.request_id),
        request_hash=request_hash,
        revision=body.expected_revision + 1,
        question=body.question,
        response=response_json,
        source_hash=response_hash,
        history_period=period_json,
        proposed_prices=prices,
        context_turns=dialogue.context_turns,
    )
    db.add(row)
    db.commit()
    return TurnResponse(
        id=row.id,
        conversation_id=conversation_id,
        request_id=row.request_id,
        revision=row.revision,
        question=row.question,
        answer=response,
        answer_status="available",
        context_turns=row.context_turns,
        created_at=row.created_at,
    )
