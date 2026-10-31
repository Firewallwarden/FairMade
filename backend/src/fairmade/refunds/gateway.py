"""Refund provider port; approval policy remains in the refund service."""

from typing import Protocol


class RefundGateway(Protocol):
    merchant_id: str

    def refund(
        self,
        capture_id: str,
        refund_request_id: str,
        amount_minor: int,
        request_id: str,
    ) -> str: ...

    def fetch_capture(self, capture_id: str) -> dict: ...
    def fetch_refund(self, refund_id: str) -> dict: ...
