"""Refund domain failures with safe HTTP-facing codes."""


class RefundError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status


def missing() -> RefundError:
    return RefundError("NOT_FOUND", "The requested resource was not found.", 404)
