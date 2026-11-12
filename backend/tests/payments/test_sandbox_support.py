import pytest
from payments import sandbox_support
from payments.sandbox_support import approval_url, wait_for_approval

from fairmade.payments.errors import ProviderError


def test_accepts_only_the_provider_returned_sandbox_order_link():
    url = "https://www.sandbox.paypal.com/checkoutnow?token=SYNTHETIC123"
    order = {"links": [{"rel": "approve", "method": "GET", "href": url}]}
    assert approval_url(order, "SYNTHETIC123") == url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.paypal.com/checkoutnow?token=SYNTHETIC123",
        "http://www.sandbox.paypal.com/checkoutnow?token=SYNTHETIC123",
        "https://www.sandbox.paypal.com.attacker.invalid/checkoutnow?token=SYNTHETIC123",
        "https://attacker@www.sandbox.paypal.com/checkoutnow?token=SYNTHETIC123",
        "https://www.sandbox.paypal.com:8443/checkoutnow?token=SYNTHETIC123",
        "https://www.sandbox.paypal.com/checkoutnow?token=OTHERORDER",
        "https://www.sandbox.paypal.com/checkoutnow?token=SYNTHETIC123&token=OTHERORDER",
        "https://www.sandbox.paypal.com/checkoutnow?token=SYNTHETIC123#redirect",
    ],
)
def test_rejects_live_hosts_and_unrelated_or_ambiguous_order_links(url):
    order = {"links": [{"rel": "approve", "method": "GET", "href": url}]}
    with pytest.raises(ValueError, match="sandbox order"):
        approval_url(order, "SYNTHETIC123")


@pytest.mark.parametrize(
    "links", [None, [None], [{"rel": "approve", "method": "GET", "href": 123}]]
)
def test_rejects_malformed_provider_link_metadata(links):
    with pytest.raises(ValueError, match="sandbox order"):
        approval_url({"links": links}, "SYNTHETIC123")


@pytest.fixture
def approval_clock(monkeypatch):
    elapsed = [0]
    monkeypatch.setattr(sandbox_support, "monotonic", lambda: elapsed[0])

    def advance(seconds):
        elapsed[0] += seconds

    monkeypatch.setattr(sandbox_support, "sleep", advance)
    return elapsed


def test_approval_survives_a_temporary_provider_failure(approval_clock):
    responses = iter([ProviderError(), {"status": "CREATED"}, {"status": "APPROVED"}])
    fetched = []

    def fetch(order_id):
        fetched.append(order_id)
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    assert wait_for_approval(fetch, "SYNTHETIC123") == {"status": "APPROVED"}
    assert fetched == ["SYNTHETIC123"] * 3


@pytest.mark.parametrize("unavailable", [False, True])
def test_approval_wait_remains_bounded_when_unconfirmed(approval_clock, unavailable):
    def fetch(_order_id):
        if unavailable:
            raise ProviderError()
        return {"status": "CREATED"}

    with pytest.raises(TimeoutError, match="local history is retained"):
        wait_for_approval(fetch, "SYNTHETIC123", timeout_seconds=6)
    assert approval_clock[0] == 6


@pytest.mark.parametrize("status", ["COMPLETED", "VOIDED", None])
def test_approval_wait_stops_on_an_unexpected_order_state(approval_clock, status):
    with pytest.raises(ValueError, match="inspect retained history"):
        wait_for_approval(lambda _order_id: {"status": status}, "SYNTHETIC123")
    assert approval_clock[0] == 0
