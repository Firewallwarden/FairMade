"""Verified source eligibility, immediate publication, author ownership and privacy."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from fairmade.main import create_app
from fairmade.models import PayPalCheckout, ProductReview

BACKEND = Path(__file__).parents[2]
OWN = "/api/v1/account/product-reviews"
CONTENT = {"rating": 4, "text": "Synthetic buyer opinion.", "publish": True}


@pytest.fixture
def paid(paypal_client, buyer_headers, unpaid_order, checkout_path, checkout, fake_gateway):
    fake_gateway.approve(checkout["provider_order_id"])
    response = paypal_client.post(checkout_path + "/capture", headers=buyer_headers, json={})
    assert response.status_code == 200 and response.json()["state"] == "completed"
    return unpaid_order


def purchase_path(order, listing_id):
    return "/api/v1/orders/" + order["id"] + "/listings/" + listing_id + "/review"


def public_path(order_source):
    return "/api/v1/marketplace/listings/" + order_source["listing"]["id"] + "/reviews"


@pytest.fixture
def review(paypal_client, paid, buyer_headers, order_source):
    response = paypal_client.post(
        purchase_path(paid, order_source["listing"]["id"]), headers=buyer_headers, json=CONTENT
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_verified_purchase_publishes_immediately_without_pickup_or_seller_approval(
    paypal_client,
    paid,
    review,
    buyer_headers,
    order_source,
):
    page = paypal_client.get(public_path(order_source))
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    assert len(page.json()["items"]) == 1
    public = page.json()["items"][0]
    assert public["id"] == review["id"] and public["rating"] == 4
    assert public["text"] == CONTENT["text"]
    assert public["reviewer_label"] == "Verified sandbox buyer"
    assert public["purchase_basis"] == "sandbox_capture_verified_at_submission"
    assert public["claims_basis"] == "buyer_reported_unverified"
    assert public["created_at"].endswith("Z")
    for secret in (
        "buyer_account_id",
        "product_id",
        "order_id",
        "capture",
        "email",
        "purchase_verified_at",
    ):
        if secret == "capture":
            assert "CAPTURE000" not in page.text
        else:
            assert secret not in public
    assert paypal_client.get(OWN, headers=buyer_headers).json()["items"] == [review]
    assert "product_id" not in review and "purchase_capture_id" not in review
    assert paypal_client.get(OWN + "/" + review["id"], headers=buyer_headers).json() == review
    summary = paypal_client.get(public_path(order_source) + "/summary").json()
    assert summary["review_count"] == 1 and summary["average_rating"] == "4.00"
    assert summary["notices"]


def test_duplicate_create_is_retry_safe_and_conflicting_body_requires_author_edit(
    paypal_client,
    paid,
    buyer_headers,
    order_source,
    review,
):
    path = purchase_path(paid, order_source["listing"]["id"])
    repeated = paypal_client.post(path, headers=buyer_headers, json=CONTENT)
    assert repeated.status_code == 200 and repeated.json() == review
    conflict = paypal_client.post(path, headers=buyer_headers, json={**CONTENT, "rating": 2})
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "REVIEW_EXISTS"


@pytest.mark.parametrize("state", ["absent", "ready", "capture_pending", "needs_review", "failed"])
def test_unpaid_or_uncertain_capture_does_not_authorize_review(
    paypal_client,
    unpaid_order,
    buyer_headers,
    checkout,
    order_source,
    state,
):
    with Session(paypal_client.app.state.engine) as db, db.begin():
        payment = db.get(PayPalCheckout, unpaid_order["id"])
        if state == "absent":
            db.delete(payment)
        else:
            payment.state = state
    response = paypal_client.post(
        purchase_path(unpaid_order, order_source["listing"]["id"]),
        headers=buyer_headers,
        json=CONTENT,
    )
    assert (
        response.status_code == 409 and response.json()["detail"]["code"] == "PURCHASE_NOT_VERIFIED"
    )
    assert paypal_client.get(public_path(order_source)).json()["items"] == []


def test_foreign_orders_missing_lines_and_seller_edits_are_denied(
    paypal_client,
    paid,
    buyer_headers,
    market_headers,
    market_account,
    order_source,
    review,
):
    source = purchase_path(paid, order_source["listing"]["id"])
    assert paypal_client.post(source, json=CONTENT).status_code == 401
    assert paypal_client.post(source, headers=market_headers, json=CONTENT).status_code == 404
    assert (
        paypal_client.post(
            purchase_path(paid, str(uuid4())), headers=buyer_headers, json=CONTENT
        ).status_code
        == 404
    )
    stranger = market_account("stranger-review@example.com")
    for headers in (market_headers, stranger):
        path = OWN + "/" + review["id"]
        assert paypal_client.get(path, headers=headers).status_code == 404
        assert (
            paypal_client.put(
                path, headers=headers, json={**CONTENT, "expected_revision": 1}
            ).status_code
            == 404
        )
        assert (
            paypal_client.post(
                path + "/withdraw", headers=headers, json={"expected_revision": 1}
            ).status_code
            == 404
        )
    assert paypal_client.get(OWN, headers=market_headers).json()["items"] == []


def test_author_edits_withdraws_and_explicitly_republishes_using_revisions(
    paypal_client,
    buyer_headers,
    order_source,
    review,
):
    path = OWN + "/" + review["id"]
    changed = {**CONTENT, "rating": 2, "text": "Changed opinion.", "expected_revision": 1}
    response = paypal_client.put(path, headers=buyer_headers, json=changed)
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert paypal_client.put(path, headers=buyer_headers, json=changed).json() == response.json()
    assert (
        paypal_client.put(
            path, headers=buyer_headers, json={**CONTENT, "expected_revision": 1}
        ).status_code
        == 409
    )
    for _ in range(2):
        assert (
            paypal_client.post(
                path + "/withdraw", headers=buyer_headers, json={"expected_revision": 2}
            ).status_code
            == 204
        )
    assert paypal_client.get(public_path(order_source)).json()["items"] == []
    summary = paypal_client.get(public_path(order_source) + "/summary").json()
    assert summary["review_count"] == 0 and summary["average_rating"] is None
    assert paypal_client.get(path, headers=buyer_headers).json()["state"] == "withdrawn"
    assert (
        paypal_client.put(
            path, headers=buyer_headers, json={**CONTENT, "expected_revision": 3}
        ).status_code
        == 200
    )
    assert len(paypal_client.get(public_path(order_source)).json()["items"]) == 1


def test_refund_request_does_not_suppress_existing_review_or_expose_financial_data(
    paypal_client,
    paid,
    buyer_headers,
    order_source,
    review,
):
    before = paypal_client.get(public_path(order_source)).json()
    refund = paypal_client.post(
        "/api/v1/orders/" + paid["id"] + "/refund-request",
        headers=buyer_headers,
        json={"reason": "PRIVATE_REFUND_REASON"},
    )
    assert refund.status_code == 201
    after = paypal_client.get(public_path(order_source))
    assert after.json() == before and "PRIVATE_REFUND" not in after.text


def test_catalog_withdrawal_hides_all_review_pages_without_deleting_feedback(
    paypal_client,
    market_headers,
    buyer_headers,
    order_source,
    review,
):
    paypal_client.post(order_source["path"] + "/listing/deactivate", headers=market_headers)
    for suffix in ("", "/summary"):
        assert paypal_client.get(public_path(order_source) + suffix).status_code == 404
    assert paypal_client.get(OWN + "/" + review["id"], headers=buyer_headers).status_code == 200
    preview = paypal_client.get(
        order_source["path"] + "/listing/preview", headers=market_headers
    ).json()
    result = paypal_client.post(
        order_source["path"] + "/listing/activate",
        headers=market_headers,
        json={
            "expected_revision": preview["revision"],
            "preview_hash": preview["preview_hash"],
            "approved": True,
        },
    )
    assert result.status_code == 200
    assert paypal_client.get(public_path(order_source)).json()["items"][0]["id"] == review["id"]


@pytest.mark.parametrize(
    "change",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": True},
        {"rating": 1.5},
        {"text": " "},
        {"text": "\x00"},
        {"text": "x" * 2001},
        {"publish": False},
        {"publish": "true"},
        {"buyer_account_id": "PRIVATE_BUYER"},
        {"purchase_capture_id": "PRIVATE_CAPTURE"},
    ],
)
def test_validation_and_consent_reject_forged_or_oversized_input(
    paypal_client,
    paid,
    buyer_headers,
    order_source,
    change,
):
    response = paypal_client.post(
        purchase_path(paid, order_source["listing"]["id"]),
        headers=buyer_headers,
        json={**CONTENT, **change},
    )
    assert response.status_code == 422 and response.headers["Cache-Control"] == "no-store"
    assert "PRIVATE_BUYER" not in response.text and "PRIVATE_CAPTURE" not in response.text
    assert all("input" not in item for item in response.json()["detail"])


def test_duplicate_create_race_produces_one_review(
    paypal_client, paid, buyer_headers, order_source
):
    path = purchase_path(paid, order_source["listing"]["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: paypal_client.post(path, headers=buyer_headers, json=CONTENT), range(2)
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert len(paypal_client.get(public_path(order_source)).json()["items"]) == 1


def test_competing_edits_protect_revision(paypal_client, buyer_headers, review):
    path = OWN + "/" + review["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda rating: paypal_client.put(
                    path,
                    headers=buyer_headers,
                    json={**CONTENT, "rating": rating, "expected_revision": 1},
                ),
                [1, 5],
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert paypal_client.get(path, headers=buyer_headers).json()["revision"] == 2


def test_failed_commit_publishes_nothing(
    paypal_client,
    paid,
    buyer_headers,
    order_source,
    market_url,
):
    def fail(db):
        if any(isinstance(row, ProductReview) for row in db.new):
            raise RuntimeError("Synthetic review persistence failure")

    event.listen(Session, "before_commit", fail)
    try:
        with TestClient(create_app(market_url), raise_server_exceptions=False) as client:
            assert (
                client.post(
                    purchase_path(paid, order_source["listing"]["id"]),
                    headers=buyer_headers,
                    json=CONTENT,
                ).status_code
                == 500
            )
    finally:
        event.remove(Session, "before_commit", fail)
    assert paypal_client.get(public_path(order_source)).json()["items"] == []


def test_restart_metadata_and_downgrade_protect_purchase_evidence(
    paypal_client,
    buyer_headers,
    order_source,
    review,
    market_url,
):
    before = paypal_client.get(public_path(order_source)).json()
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    with pytest.raises(RuntimeError, match="product review records"):
        command.downgrade(config, "0017")
    command.check(config)
    with TestClient(create_app(market_url)) as restarted:
        assert restarted.get(public_path(order_source)).json() == before
    with paypal_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    with Session(paypal_client.app.state.engine) as db:
        source = db.scalar(select(ProductReview))
        assert source.purchase_capture_id and source.purchase_verified_at


def test_openapi_separates_auth_and_anonymous_review_reads(paypal_client):
    schema = paypal_client.get("/openapi.json").json()
    for path, operations in schema["paths"].items():
        if "product-reviews" in path or (
            path.startswith("/api/v1/orders/") and path.endswith("/review")
        ):
            assert all(
                operation["security"] == [{"HTTPBearer": []}] for operation in operations.values()
            )
        if path.startswith("/api/v1/marketplace/listings/") and "/reviews" in path:
            assert all("security" not in operation for operation in operations.values())


def test_one_buyer_cannot_add_another_review_after_repeat_purchase(
    paypal_client,
    buyer_headers,
    paid,
    review,
    cart,
    fake_gateway,
    order_source,
):
    order = paypal_client.post(
        "/api/v1/orders", headers={**buyer_headers, "Idempotency-Key": str(uuid4())}, json=cart
    ).json()
    path = "/api/v1/orders/" + order["id"] + "/paypal-checkout"
    checkout = paypal_client.post(path, headers=buyer_headers, json={}).json()
    fake_gateway.approve(checkout["provider_order_id"])
    assert paypal_client.post(path + "/capture", headers=buyer_headers, json={}).status_code == 200
    response = paypal_client.post(
        purchase_path(order, order_source["listing"]["id"]), headers=buyer_headers, json=CONTENT
    )
    assert response.status_code == 409 and response.json()["detail"]["code"] == "REVIEW_EXISTS"
    assert len(paypal_client.get(public_path(order_source)).json()["items"]) == 1


def test_rating_summary_counts_buyers_once_and_uses_exact_decimal_average(
    paypal_client,
    review,
    cart,
    fake_gateway,
    order_source,
    market_account,
):
    authors = []
    for number, rating in enumerate((1, 2)):
        # Seller accounts also retain general buyer capabilities when buying from others.
        headers = market_account(
            f"rating-buyer-{number}@example.com", roles=("seller",) if number == 0 else ()
        )
        order = paypal_client.post(
            "/api/v1/orders", headers={**headers, "Idempotency-Key": str(uuid4())}, json=cart
        ).json()
        path = "/api/v1/orders/" + order["id"] + "/paypal-checkout"
        checkout = paypal_client.post(path, headers=headers, json={}).json()
        fake_gateway.approve(checkout["provider_order_id"])
        assert paypal_client.post(path + "/capture", headers=headers, json={}).status_code == 200
        response = paypal_client.post(
            purchase_path(order, order_source["listing"]["id"]),
            headers=headers,
            json={**CONTENT, "rating": rating},
        )
        assert response.status_code == 201, response.text
        authors.append((headers, response.json()))
    summary = paypal_client.get(public_path(order_source) + "/summary").json()
    assert summary["review_count"] == 3 and summary["average_rating"] == "2.33"
    headers, last = authors[-1]
    assert (
        paypal_client.post(
            OWN + "/" + last["id"] + "/withdraw", headers=headers, json={"expected_revision": 1}
        ).status_code
        == 204
    )
    summary = paypal_client.get(public_path(order_source) + "/summary").json()
    assert summary["review_count"] == 2 and summary["average_rating"] == "2.50"
    page = paypal_client.get(public_path(order_source) + "?limit=1&offset=1").json()
    assert len(page["items"]) == 1 and page["limit"] == 1 and page["offset"] == 1
