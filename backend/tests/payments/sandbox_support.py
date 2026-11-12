"""Keep a human approval handoff restricted to the returned sandbox order."""

from urllib.parse import parse_qs, urlsplit


def approval_url(order: dict, provider_order_id: str) -> str:
    links = order.get("links")
    if not isinstance(links, list):
        raise ValueError("No supported approval link for this sandbox order was returned.")
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") not in ("approve", "payer-action") or link.get("method") != "GET":
            continue
        candidate = link.get("href", "")
        if not isinstance(candidate, str):
            continue
        try:
            url = urlsplit(candidate)
            valid = (
                url.scheme == "https"
                and url.hostname in ("www.sandbox.paypal.com", "sandbox.paypal.com")
                and url.port in (None, 443)
                and url.username is None
                and url.password is None
                and not url.fragment
                and url.path == "/checkoutnow"
                and parse_qs(url.query).get("token") == [provider_order_id]
            )
        except ValueError:
            valid = False
        if valid:
            return candidate
    raise ValueError("No supported approval link for this sandbox order was returned.")
