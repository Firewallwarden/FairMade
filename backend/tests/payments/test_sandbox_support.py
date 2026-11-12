import pytest
from payments.sandbox_support import approval_url


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
