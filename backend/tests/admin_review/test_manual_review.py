"""Manual approval is privileged, audited, atomic and independent of seller privileges."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from fairmade.admin_bootstrap import BootstrapError, BootstrapRequest, main, provision
from fairmade.main import create_app
from fairmade.models import (
    AccountRole,
    AdminBootstrapRecord,
    LoginSession,
    SellerApplication,
    SellerApplicationDecision,
)

BACKEND = Path(__file__).parents[2]
QUEUE = "/api/v1/admin/seller-applications"
OWN = "/api/v1/seller-applications"
REASON = "Synthetic review completed; access approved for local testing."


@pytest.fixture
def applicant(market_account, market_client):
    headers = market_account("applicant-review@example.com", roles=())
    created = market_client.post(OWN, headers=headers, json={})
    assert created.status_code == 201
    return headers, created.json()


@pytest.fixture
def admin(market_account):
    # Synthetic grants exercise admin HTTP behavior; real bootstrap is tested below.
    return market_account("manual-review-admin@example.com", roles=("admin",))


def decision(client, headers, application, *, outcome="approved", revision=1, reason=REASON):
    return client.post(
        QUEUE + "/" + application["id"] + "/decision",
        headers=headers,
        json={"expected_revision": revision, "outcome": outcome, "reason": reason},
    )


def test_manual_approval_grants_seller_additively_and_shares_only_safe_outcome(
    market_client,
    applicant,
    admin,
):
    headers, application = applicant
    assert application["status"] == "pending" and application["revision"] == 1
    assert application["decision"] is None
    assert market_client.get("/api/v1/products", headers=headers).status_code == 403
    result = decision(market_client, admin, application)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["status"] == "approved" and data["revision"] == 2
    assert data["decision"]["basis"] == "manual_administrator_review"
    assert data["decision"]["created_at"].endswith("Z")
    assert (
        data["applicant_email"] == "applicant-review@example.com" and data["decided_by_account_id"]
    )
    own = market_client.get(OWN + "/me", headers=headers)
    assert own.status_code == 200 and own.json()["decision"]["reason"] == REASON
    assert "decided_by_account_id" not in own.text and "applicant_email" not in own.text
    assert market_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == [
        "buyer",
        "seller",
    ]
    assert market_client.get("/api/v1/products", headers=headers).status_code == 200
    assert market_client.get("/api/v1/products", headers=admin).status_code == 403
    assert result.headers["Cache-Control"] == "no-store"
    assert "password" not in result.text and "access_token" not in result.text
    assert market_client.get("/api/v1/storefronts").json()["items"] == []


def test_denial_does_not_grant_access_and_reapplication_cannot_overwrite_decision(
    market_client,
    applicant,
    admin,
):
    headers, application = applicant
    denied = decision(
        market_client, admin, application, outcome="denied", reason="More review is needed."
    )
    assert denied.status_code == 200 and denied.json()["status"] == "denied"
    assert market_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == ["buyer"]
    assert market_client.get("/api/v1/products", headers=headers).status_code == 403
    repeated = market_client.post(OWN, headers=headers, json={})
    assert repeated.status_code == 200 and repeated.json()["status"] == "denied"
    assert decision(market_client, admin, application).status_code == 409


def test_exact_retry_preserves_audit_and_never_regrants_revoked_role(
    market_client, applicant, admin
):
    headers, application = applicant
    original = decision(market_client, admin, application)
    assert decision(market_client, admin, application).json() == original.json()
    account_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with Session(market_client.app.state.engine) as db, db.begin():
        assert len(db.scalars(select(SellerApplicationDecision)).all()) == 1
        db.execute(
            delete(AccountRole).where(
                AccountRole.account_id == account_id, AccountRole.role == "seller"
            )
        )
    assert decision(market_client, admin, application).json() == original.json()
    assert market_client.get("/api/v1/products", headers=headers).status_code == 403


def test_non_admins_and_self_review_are_denied(market_client, applicant, market_account, admin):
    headers, application = applicant
    seller = market_account("seller-only-review@example.com")
    for actor, code in (({}, 401), (headers, 403), (seller, 403)):
        assert market_client.get(QUEUE, headers=actor).status_code == code
        assert market_client.get(QUEUE + "/" + application["id"], headers=actor).status_code == code
        assert decision(market_client, actor, application).status_code == code
    own_app = market_client.post(OWN, headers=admin, json={}).json()
    response = decision(market_client, admin, own_app)
    assert (
        response.status_code == 403 and response.json()["detail"]["code"] == "SELF_REVIEW_FORBIDDEN"
    )
    assert market_client.get("/api/v1/auth/me", headers=admin).json()["roles"] == ["buyer", "admin"]
    assert market_client.get(QUEUE + "/" + str(uuid4()), headers=admin).status_code == 404


def test_stale_revisions_and_existing_seller_access_do_not_create_decisions(
    market_client,
    applicant,
    admin,
):
    headers, application = applicant
    assert (
        decision(market_client, admin, application, revision=2).json()["detail"]["code"]
        == "REVISION_CONFLICT"
    )
    account_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with Session(market_client.app.state.engine) as db, db.begin():
        db.add(AccountRole(account_id=account_id, role="seller"))
    result = decision(market_client, admin, application)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "SELLER_ALREADY_GRANTED"
    assert (
        market_client.get(QUEUE + "/" + application["id"], headers=admin).json()["status"]
        == "pending"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"outcome": "admin"},
        {"expected_revision": 0},
        {"expected_revision": True},
        {"reason": " "},
        {"reason": "x" * 2001},
        {"reason": "\x00"},
        {"role": "PRIVATE_FORGED_ROLE"},
        {"decided_by_account_id": "PRIVATE_ACTOR"},
    ],
)
def test_decision_input_is_bounded_and_redacted(market_client, applicant, admin, change):
    _, application = applicant
    response = market_client.post(
        QUEUE + "/" + application["id"] + "/decision",
        headers=admin,
        json={"expected_revision": 1, "outcome": "approved", "reason": REASON, **change},
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_FORGED" not in response.text and "PRIVATE_ACTOR" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_competing_decisions_record_one_atomic_outcome(market_client, applicant, admin):
    headers, application = applicant
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda outcome: decision(market_client, admin, application, outcome=outcome),
                ["approved", "denied"],
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    result = market_client.get(OWN + "/me", headers=headers).json()
    roles = market_client.get("/api/v1/auth/me", headers=headers).json()["roles"]
    assert ("seller" in roles) == (result["status"] == "approved")
    with Session(market_client.app.state.engine) as db:
        assert len(db.scalars(select(SellerApplicationDecision)).all()) == 1


def test_failed_decision_commit_rolls_back_audit_status_and_role(
    market_client, applicant, admin, market_url
):
    headers, application = applicant

    def fail(db):
        if any(isinstance(row, SellerApplicationDecision) for row in db.new):
            raise RuntimeError("Synthetic review commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert decision(client, admin, application).status_code == 500
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get(OWN + "/me", headers=headers).json()["status"] == "pending"
    assert market_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == ["buyer"]
    with Session(market_client.app.state.engine) as db:
        assert db.scalars(select(SellerApplicationDecision)).all() == []


def test_admin_queue_pagination_filter_and_applicant_isolation(
    market_client, applicant, admin, market_account
):
    headers, application = applicant
    other = market_account("other-applicant@example.com", roles=())
    second = market_client.post(OWN, headers=other, json={}).json()
    pending = market_client.get(QUEUE + "?limit=1&offset=1", headers=admin).json()
    assert [row["id"] for row in pending["items"]] == [second["id"]]
    decision(market_client, admin, application)
    assert [row["id"] for row in market_client.get(QUEUE, headers=admin).json()["items"]] == [
        second["id"]
    ]
    assert (
        market_client.get(QUEUE + "?state=approved", headers=admin).json()["items"][0]["id"]
        == application["id"]
    )
    assert len(market_client.get(QUEUE + "?state=all", headers=admin).json()["items"]) == 2
    assert market_client.get(OWN + "/me", headers=other).json()["id"] == second["id"]


def test_restart_schema_and_downgrade_guard_preserve_decision(
    market_client, applicant, admin, market_url
):
    headers, application = applicant
    expected = decision(market_client, admin, application).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="seller decision records"):
        command.downgrade(config, "0018")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(QUEUE + "/" + application["id"], headers=admin).json() == expected
        assert restarted.get("/api/v1/products", headers=headers).status_code == 200
    with market_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_first_admin_bootstrap_is_audited_and_revokes_old_sessions(
    market_client, applicant, capsys
):
    headers, _ = applicant
    account_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    assert main(["--account-id", account_id, "--reason", "Synthetic local operator bootstrap"]) == 0
    assert "sign in again" in capsys.readouterr().out
    assert market_client.get("/api/v1/auth/me", headers=headers).status_code == 401
    with Session(market_client.app.state.engine) as db:
        assert db.get(AccountRole, (account_id, "admin")) is not None
        assert db.get(AccountRole, (account_id, "seller")) is None
        assert db.get(AdminBootstrapRecord, 1).account_id == account_id
        assert (
            db.scalars(select(LoginSession).where(LoginSession.account_id == account_id)).all()
            == []
        )
    assert (
        main(["--account-id", account_id, "--reason", "Different retry reason is not a new event"])
        == 0
    )
    assert "already provisioned" in capsys.readouterr().out


def test_bootstrap_cannot_add_more_admins_or_restore_revoked_privileges(
    market_client, applicant, market_account
):
    headers, _ = applicant
    first_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    other_headers = market_account("second-bootstrap@example.com", roles=())
    other_id = market_client.get("/api/v1/auth/me", headers=other_headers).json()["id"]
    with Session(market_client.app.state.engine, expire_on_commit=False) as db:
        assert provision(db, BootstrapRequest(account_id=first_id, reason="Synthetic bootstrap"))
        with pytest.raises(BootstrapError):
            provision(db, BootstrapRequest(account_id=other_id, reason="Not permitted"))
        db.rollback()
        db.execute(
            delete(AccountRole).where(
                AccountRole.account_id == first_id, AccountRole.role == "admin"
            )
        )
        db.commit()
        with pytest.raises(BootstrapError):
            provision(db, BootstrapRequest(account_id=first_id, reason="Cannot silently restore"))


def test_existing_admin_prevents_bootstrap_and_invalid_input_is_safe(
    market_client, applicant, admin, capsys
):
    headers, _ = applicant
    account_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    assert main(["--account-id", account_id, "--reason", "PRIVATE_BOOTSTRAP_REASON"]) == 2
    assert "PRIVATE_BOOTSTRAP_REASON" not in capsys.readouterr().err
    assert main(["--account-id", "PRIVATE_INVALID_ID", "--reason", "PRIVATE_REASON"]) == 2
    assert "PRIVATE_INVALID" not in capsys.readouterr().err


def test_bootstrap_failure_rolls_back_role_record_and_session_revocation(market_client, applicant):
    headers, _ = applicant
    account_id = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]

    def fail(db):
        raise RuntimeError("Synthetic bootstrap commit failure")

    event.listen(Session, "before_commit", fail)
    try:
        with Session(market_client.app.state.engine) as db:
            with pytest.raises(RuntimeError):
                provision(db, BootstrapRequest(account_id=account_id, reason="Synthetic bootstrap"))
    finally:
        event.remove(Session, "before_commit", fail)
    assert market_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    with Session(market_client.app.state.engine) as db:
        assert db.get(AdminBootstrapRecord, 1) is None
        assert db.get(AccountRole, (account_id, "admin")) is None


def test_pending_application_roundtrip_preserves_identity_and_no_automatic_role(
    market_client, applicant
):
    headers, before = applicant
    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "0018")
    command.upgrade(config, "head")
    command.check(config)
    assert market_client.get(OWN + "/me", headers=headers).json() == before
    assert market_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == ["buyer"]


def test_openapi_has_no_public_role_grant_or_bootstrap_endpoint(market_client):
    schema = market_client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        assert "bootstrap" not in path
        if path.startswith(QUEUE):
            assert all(
                operation["security"] == [{"HTTPBearer": []}] for operation in operations.values()
            )


def test_competing_first_admin_bootstraps_provision_only_one_account(
    market_client,
    applicant,
    market_account,
):
    headers, _ = applicant
    first = market_client.get("/api/v1/auth/me", headers=headers).json()["id"]
    other_headers = market_account("bootstrap-race@example.com", roles=())
    second = market_client.get("/api/v1/auth/me", headers=other_headers).json()["id"]

    def attempt(account_id):
        with Session(market_client.app.state.engine, expire_on_commit=False) as db:
            try:
                return provision(
                    db, BootstrapRequest(account_id=account_id, reason="Synthetic operator race")
                )
            except BootstrapError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [first, second]))
    assert sorted(results) == [False, True]
    with Session(market_client.app.state.engine) as db:
        assert len(db.scalars(select(AccountRole).where(AccountRole.role == "admin")).all()) == 1
        assert db.get(AdminBootstrapRecord, 1).account_id in (first, second)


def test_nonpending_application_without_audit_cannot_be_silently_repaired(
    market_client,
    applicant,
    admin,
):
    headers, application = applicant
    with Session(market_client.app.state.engine) as db, db.begin():
        db.get(SellerApplication, application["id"]).status = "approved"
    response = decision(market_client, admin, application)
    assert (
        response.status_code == 409
        and response.json()["detail"]["code"] == "APPLICATION_NOT_PENDING"
    )
    assert market_client.get("/api/v1/auth/me", headers=headers).json()["roles"] == ["buyer"]
