import pytest
from sqlalchemy.orm import Session

from fairmade.models import SupplierComparison


@pytest.mark.parametrize(
    "mode,indices",
    [
        ("savings", [0]),
        ("quality", [1]),
        ("balanced", [0, 1]),
    ],
)
def test_modes_preserve_mandatory_exclusions_and_show_tradeoffs(
    market_client, market_headers, supplier_body, mode, indices
):
    source, body = supplier_body
    response = market_client.post(
        source["recommendation_path"], headers=market_headers, json={**body, "mode": mode}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert set(result["selected_quote_ids"]) == {source["ids"][index] for index in indices}
    excluded = result["rows"][3]
    assert excluded["eligible"] is False and excluded["cost"] is None
    assert excluded["objective_cost"] is None and excluded["selected_for_input_review"] is False
    assert "QUALITY_FAILED" in excluded["exclusion_reasons"]
    assert result["product_impact"] == "not_assessed_no_substitution_authorized"
    assert "PRIVATE_SUPPLIER_NOTES" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with Session(market_client.app.state.engine) as db:
        assert (
            db.get(SupplierComparison, source["report"]["id"]).result == source["report"]["result"]
        )


def test_quality_priority_order_and_no_preferences(market_client, market_headers, supplier_body):
    source, body = supplier_body
    local = {"key": "local", "label": "Local claim", "type": "boolean", "expected": True}
    request = {**body, "mode": "quality", "preferences": [local, *body["preferences"]]}
    result = market_client.post(source["recommendation_path"], headers=market_headers, json=request)
    assert result.status_code == 200
    assert result.json()["selected_quote_ids"] == [source["ids"][0]]
    for mode in ("savings", "quality", "balanced"):
        result = market_client.post(
            source["recommendation_path"],
            headers=market_headers,
            json={**body, "mode": mode, "preferences": []},
        )
        assert result.json()["selected_quote_ids"] == [source["ids"][0]]


def test_ties_and_unknown_optional_claims_stay_distinct_from_mandatory_failure(
    market_client, market_headers, supplier_scope
):
    source = supplier_scope(
        [
            ("Equal left", "10.00", True, True, False),
            ("Equal right", "10.00", True, True, False),
        ]
    )
    body = {
        "supplier_report_id": source["report"]["id"],
        "preferences": [
            {
                "key": "unreported",
                "label": "Unknown optional claim",
                "type": "boolean",
                "expected": True,
            }
        ],
    }
    response = market_client.post(source["recommendation_path"], headers=market_headers, json=body)
    assert response.status_code == 200
    assert set(response.json()["selected_quote_ids"]) == set(source["ids"])
    assert all(
        row["eligible"] and row["preference_checks"][0]["status"] == "unknown"
        for row in response.json()["rows"]
    )


def test_current_input_locks_replace_saved_eligibility(
    market_client, market_headers, supplier_body
):
    source, body = supplier_body
    updated = market_client.put(
        source["supplier_path"] + "/quality-locks",
        headers=market_headers,
        json={
            "expected_revision": 1,
            "rules": [
                {
                    "key": "new_requirement",
                    "label": "New requirement",
                    "type": "boolean",
                    "expected": True,
                }
            ],
        },
    )
    assert updated.status_code == 200
    response = market_client.post(source["recommendation_path"], headers=market_headers, json=body)
    assert response.status_code == 200
    assert response.json()["rule_revision"] == 2 and response.json()["selected_quote_ids"] == []
    assert all("QUALITY_UNKNOWN" in row["exclusion_reasons"] for row in response.json()["rows"])


def test_auth_role_ownership_and_foreign_report(
    market_client, market_headers, buyer_headers, market_account, market_source, supplier_body
):
    source, body = supplier_body
    path = source["recommendation_path"]
    assert market_client.post(path, json=body).status_code == 401
    assert market_client.post(path, headers=buyer_headers, json=body).status_code == 403
    other = market_account("other-supplier-recommendation@example.com")
    assert market_client.post(path, headers=other, json=body).status_code == 404
    product = market_source()
    assert (
        market_client.post(
            product["path"] + "/supplier-recommendations", headers=market_headers, json=body
        ).status_code
        == 404
    )


def test_bounded_private_input(market_client, market_headers, supplier_body):
    source, body = supplier_body
    invalid = [
        {**body, "mode": "highest_profit"},
        {**body, "cost_objective": "guess"},
        {**body, "preferences": body["preferences"] * 2},
        {
            **body,
            "preferences": [
                {
                    "key": f"preference_{index}",
                    "label": "Optional",
                    "type": "boolean",
                    "expected": True,
                }
                for index in range(9)
            ],
        },
        {**body, "private": "PRIVATE_FAKE_VALUE"},
    ]
    for request in invalid:
        response = market_client.post(
            source["recommendation_path"], headers=market_headers, json=request
        )
        assert response.status_code == 422 and "PRIVATE_FAKE_VALUE" not in response.text


def test_purchase_outlay_and_usable_unit_are_separate_objectives(
    market_client, market_headers, supplier_scope
):
    source = supplier_scope(package_quantities={1: "4"})
    request = {"supplier_report_id": source["report"]["id"], "mode": "savings"}
    left = market_client.post(source["recommendation_path"], headers=market_headers, json=request)
    right = market_client.post(
        source["recommendation_path"],
        headers=market_headers,
        json={**request, "cost_objective": "usable_unit"},
    )
    assert left.status_code == right.status_code == 200
    assert left.json()["selected_quote_ids"] == [source["ids"][0]]
    assert right.json()["selected_quote_ids"] == [source["ids"][1]]
