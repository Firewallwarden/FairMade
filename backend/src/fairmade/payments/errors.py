"""Safe errors that never expose provider bodies, credentials or payer data."""


class PaymentError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status


class ProviderError(Exception):
    """An external result is unavailable or uncertain; raw response text is discarded."""


class VerificationError(Exception):
    """Provider data does not establish the expected payment."""


def unavailable() -> PaymentError:
    return PaymentError(
        "PAYPAL_UNAVAILABLE", "PayPal sandbox is unavailable; retry or reconcile.", 502
    )
