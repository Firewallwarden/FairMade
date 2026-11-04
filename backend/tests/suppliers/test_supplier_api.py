"""Ownership, immutable snapshots, revision races and migration preservation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from fairmade.auth import hash_token
from fairmade.main import create_app
from fairmade.models import AccountRole, LoginSession

BACKEND = Path(__file__).parents[2]


def save_quote(client, headers, path, body):
    response = client.post(path + "/supplier-quotes", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def request_body(quote_id, revision=1):
    return {
        "quote_ids": [quote_id],
        "expected_rule_revision": revision,
        "required_quantity": {"value": "9", "unit": "kg"},
    }


def test_input_locks_quotes_reports_and_pagination(
    supplier_client,
    supplier_headers,
    product_path,
    configured_input,
    quote_body,
):
    client, headers, path = supplier_client, supplier_headers, configured_input
    quote = save_quote(client, headers, path, quote_body)
    report = client.post(
        path + "/supplier-comparisons", headers=headers, json=request_body(quote["id"])
    )
    assert report.status_code == 201, report.text
    saved = report.json()
    assert saved["rule_revision"] == 1
    assert saved["basis"] == quote["basis"] == "seller_reported_unverified"
    assert saved["result"]["rows"][0]["cost"]["purchase_cost"] == "40.00"
    assert saved["result"]["eligible_count"] == 1
    assert saved["product_snapshot"]["name"] == "Synthetic loaf"
    assert saved["sourcing_input_snapshot"]["label"] == "Bread flour"
    assert "account_id" not in saved["product_snapshot"]
    assert client.get(path + "/supplier-quotes/" + quote["id"], headers=headers).json() == quote
    assert (
        client.get(path + "/supplier-comparisons/" + saved["id"], headers=headers).json() == saved
    )
    for url in (
        product_path + "/sourcing-inputs",
        path + "/supplier-quotes",
        path + "/supplier-comparisons",
    ):
        first = client.get(url + "?limit=1&offset=0", headers=headers)
        assert first.status_code == 200
        assert len(first.json()["items"]) == 1
        assert client.get(url + "?limit=1&offset=1", headers=headers).json()["items"] == []
        for query in ("limit=0", "limit=101", "offset=-1"):
            assert client.get(url + "?" + query, headers=headers).status_code == 422
    assert saved["created_at"].endswith("Z")
    assert client.get(path, headers=headers).json()["updated_at"].endswith("Z")


def test_report_survives_rule_product_quote_and_clock_changes_and_restart(
    supplier_client,
    supplier_headers,
    configured_input,
    product_path,
    quote_body,
    supplier_url,
    monkeypatch,
):
    client, headers, path = supplier_client, supplier_headers, configured_input
    quote = save_quote(client, headers, path, quote_body)
    body = request_body(quote["id"])
    original = client.post(path + "/supplier-comparisons", headers=headers, json=body).json()
    assert (
        client.put(
            path + "/quality-locks",
            headers=headers,
            json={"expected_revision": 1, "rules": []},
        ).status_code
        == 200
    )
    assert (
        client.patch(product_path, headers=headers, json={"name": "Edited loaf"}).status_code == 200
    )
    quote_body["package_price"] = "100.00"
    save_quote(client, headers, path, quote_body)
    monkeypatch.setattr("fairmade.suppliers.workflows.today", lambda: date(2026, 3, 31))
    stale = client.post(path + "/supplier-comparisons", headers=headers, json=body)
    assert stale.status_code == 409
    body["expected_rule_revision"] = 2
    new = client.post(path + "/supplier-comparisons", headers=headers, json=body).json()
    assert new["result"]["eligible_count"] == 0
    assert "STALE_QUOTE" in new["result"]["rows"][0]["exclusion_reasons"]
    assert "QUALITY_NOT_EVALUATED" in new["result"]["rows"][0]["exclusion_reasons"]
    with TestClient(create_app(supplier_url)) as restarted:
        assert (
            restarted.get(path + "/supplier-comparisons/" + original["id"], headers=headers).json()
            == original
        )
        assert (
            restarted.get(path + "/supplier-quotes/" + quote["id"], headers=headers).json() == quote
        )


def test_no_requirements_no_eligibility(supplier_client, supplier_headers, input_path, quote_body):
    quote = save_quote(supplier_client, supplier_headers, input_path, quote_body)
    response = supplier_client.post(
        input_path + "/supplier-comparisons",
        headers=supplier_headers,
        json=request_body(quote["id"], 0),
    )
    assert response.status_code == 201
    result = response.json()["result"]
    assert result["eligible_count"] == 0
    assert result["lowest_purchase_cost"] is None
    assert result["rows"][0]["quality"]["status"] == "not_evaluated"


def test_all_resources_are_private_and_owner_scoped(
    supplier_client,
    supplier_headers,
    product_path,
    configured_input,
    quote_body,
    account_factory,
):
    client, headers, path = supplier_client, supplier_headers, configured_input
    quote = save_quote(client, headers, path, quote_body)
    body = request_body(quote["id"])
    report = client.post(path + "/supplier-comparisons", headers=headers, json=body).json()
    operations = [
        ("post", product_path + "/sourcing-inputs", {"label": "Private input"}),
        ("get", product_path + "/sourcing-inputs", None),
        ("get", path, None),
        ("put", path + "/quality-locks", {"expected_revision": 1, "rules": []}),
        ("post", path + "/supplier-quotes", quote_body),
        ("get", path + "/supplier-quotes", None),
        ("get", path + "/supplier-quotes/" + quote["id"], None),
        ("post", path + "/supplier-comparisons", body),
        ("get", path + "/supplier-comparisons", None),
        ("get", path + "/supplier-comparisons/" + report["id"], None),
    ]
    for auth, status in (({}, 401), (account_factory(("buyer",)), 403), (account_factory(), 404)):
        for method, url, data in operations:
            response = client.request(method, url, headers=auth, json=data)
            assert response.status_code == status, (url, response.text)
            assert quote_body["supplier_name"] not in response.text
    # A role revoked after login cannot keep using a still-valid session.
    token = headers["Authorization"].split()[1]
    with Session(client.app.state.engine) as db, db.begin():
        login = db.get(LoginSession, hash_token(token))
        grant = db.get(AccountRole, (login.account_id, "seller"))
        db.delete(grant)
    assert client.get(path, headers=headers).status_code == 403


def test_nested_ids_cannot_cross_products_or_inputs(
    supplier_client,
    supplier_headers,
    product_path,
    configured_input,
    quote_body,
):
    client, headers, path = supplier_client, supplier_headers, configured_input
    quote = save_quote(client, headers, path, quote_body)
    report = client.post(
        path + "/supplier-comparisons", headers=headers, json=request_body(quote["id"])
    ).json()
    other = client.post(
        product_path + "/sourcing-inputs",
        headers=headers,
        json={"label": "Packaging"},
    ).json()
    other_path = product_path + "/sourcing-inputs/" + other["id"]
    assert (
        client.get(other_path + "/supplier-quotes/" + quote["id"], headers=headers).status_code
        == 404
    )
    assert (
        client.get(
            other_path + "/supplier-comparisons/" + report["id"], headers=headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            other_path + "/supplier-comparisons",
            headers=headers,
            json=request_body(quote["id"], 0),
        ).status_code
        == 404
    )
    wrong_product = "/api/v1/products/" + str(uuid4()) + "/sourcing-inputs/" + other["id"]
    assert client.get(wrong_product, headers=headers).status_code == 404
    missing = request_body(str(uuid4()))
    assert (
        client.post(path + "/supplier-comparisons", headers=headers, json=missing).status_code
        == 404
    )
    assert len(client.get(path + "/supplier-comparisons", headers=headers).json()["items"]) == 1


@pytest.mark.parametrize(
    "mutation", ["duplicate", "empty", "too_many", "revision_bool", "missing_revision"]
)
def test_invalid_comparison_request(
    supplier_client,
    supplier_headers,
    configured_input,
    quote_body,
    mutation,
):
    quote = save_quote(supplier_client, supplier_headers, configured_input, quote_body)
    body = request_body(quote["id"])
    if mutation == "duplicate":
        body["quote_ids"] *= 2
    elif mutation == "empty":
        body["quote_ids"] = []
    elif mutation == "too_many":
        body["quote_ids"] = [str(uuid4()) for _ in range(101)]
    elif mutation == "revision_bool":
        body["expected_rule_revision"] = True
    else:
        del body["expected_rule_revision"]
    assert (
        supplier_client.post(
            configured_input + "/supplier-comparisons",
            headers=supplier_headers,
            json=body,
        ).status_code
        == 422
    )


def test_private_validation_does_not_echo_quote_body(
    supplier_client, supplier_headers, input_path, quote_body
):
    quote_body["supplier_name"] = "PRIVATE-SUPPLIER-MARKER"
    quote_body["unexpected"] = quote_body.copy()
    response = supplier_client.post(
        input_path + "/supplier-quotes", headers=supplier_headers, json=quote_body
    )
    assert response.status_code == 422
    assert "PRIVATE-SUPPLIER-MARKER" not in response.text
    assert all("input" not in item for item in response.json()["detail"])


def test_rules_compare_and_swap_is_atomic(supplier_client, supplier_headers, configured_input):
    def replace(label):
        return supplier_client.put(
            configured_input + "/quality-locks",
            headers=supplier_headers,
            json={
                "expected_revision": 1,
                "rules": [
                    {"key": "new", "label": label, "type": "boolean", "expected": True},
                ],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(replace, ["First revision", "Second revision"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert (
        supplier_client.get(configured_input, headers=supplier_headers).json()["rule_revision"] == 2
    )


def test_report_and_requirement_change_serialize(
    supplier_client,
    supplier_headers,
    configured_input,
    quote_body,
):
    client, headers, path = supplier_client, supplier_headers, configured_input
    quote = save_quote(client, headers, path, quote_body)

    def report():
        return client.post(
            path + "/supplier-comparisons", headers=headers, json=request_body(quote["id"])
        )

    def replace():
        return client.put(
            path + "/quality-locks", headers=headers, json={"expected_revision": 1, "rules": []}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        report_future, replace_future = pool.submit(report), pool.submit(replace)
        saved, changed = report_future.result(), replace_future.result()
    assert changed.status_code == 200
    assert saved.status_code in (201, 409)
    if saved.status_code == 201:
        assert saved.json()["rule_revision"] == 1
        assert saved.json()["result"]["eligible_count"] == 1
    assert client.get(path, headers=headers).json()["rule_revision"] == 2


def test_records_have_no_update_or_delete_routes(
    supplier_client,
    supplier_headers,
    configured_input,
    quote_body,
):
    quote = save_quote(supplier_client, supplier_headers, configured_input, quote_body)
    report = supplier_client.post(
        configured_input + "/supplier-comparisons",
        headers=supplier_headers,
        json=request_body(quote["id"]),
    ).json()
    for path in (
        configured_input + "/supplier-quotes/" + quote["id"],
        configured_input + "/supplier-comparisons/" + report["id"],
    ):
        for method in ("patch", "put", "delete"):
            assert (
                supplier_client.request(method, path, headers=supplier_headers, json={}).status_code
                == 405
            )


def test_schema_matches_migration_and_refuses_evidence_downgrade(
    supplier_client,
    supplier_headers,
    configured_input,
    quote_body,
):
    config = Config(str(BACKEND / "alembic.ini"))
    command.check(config)
    quote = save_quote(supplier_client, supplier_headers, configured_input, quote_body)
    report = supplier_client.post(
        configured_input + "/supplier-comparisons",
        headers=supplier_headers,
        json=request_body(quote["id"]),
    ).json()
    with pytest.raises(RuntimeError, match="sourcing records exist"):
        command.downgrade(config, "0010")
    assert (
        supplier_client.get(
            configured_input + "/supplier-comparisons/" + report["id"],
            headers=supplier_headers,
        ).json()
        == report
    )
    with supplier_client.app.state.engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == ScriptDirectory.from_config(config).get_current_head()
        )


def test_empty_downgrade_upgrade_preserves_existing_product(
    supplier_client,
    supplier_headers,
    product_path,
):
    config = Config(str(BACKEND / "alembic.ini"))
    with supplier_client.app.state.engine.connect() as connection:
        before = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in ("accounts", "account_roles", "sessions", "products")
        }
    command.downgrade(config, "0010")
    command.upgrade(config, "head")
    command.check(config)
    with supplier_client.app.state.engine.connect() as connection:
        for table, rows in before.items():
            assert connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all() == rows
    assert supplier_client.get(product_path, headers=supplier_headers).status_code == 200


def test_openapi_documents_strings_authorization_and_conflicts(supplier_client):
    schema = supplier_client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        if "/sourcing-inputs" in path:
            for operation in methods.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                assert {"401", "403", "404", "422"} <= set(operation["responses"])
                if "/quality-locks" in path or (
                    path.endswith("/supplier-comparisons")
                    and "post" in methods
                    and operation is methods["post"]
                ):
                    assert "409" in operation["responses"]
    models = schema["components"]["schemas"]
    assert models["SupplierQuoteCreate"]["properties"]["package_price"]["type"] == "string"
    assert models["SupplyQuantity"]["properties"]["value"]["type"] == "string"


def test_wider_downgrade_keeps_schema_intact_when_financial_guard_blocks(
    paypal_client,
    buyer_headers,
    checkout_path,
    checkout,
):
    config = Config(str(BACKEND / "alembic.ini"))
    with pytest.raises(RuntimeError, match="payment records"):
        command.downgrade(config, "0008")
    command.check(config)
    assert paypal_client.get(checkout_path, headers=buyer_headers).json() == checkout
    with paypal_client.app.state.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == ScriptDirectory.from_config(config).get_current_head()
        )
