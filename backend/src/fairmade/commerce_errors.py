"""Shared inventory/order failures, independent of HTTP and feature adapters."""


class CommerceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def missing() -> CommerceError:
    return CommerceError("NOT_FOUND", "The requested resource was not found.")


def conflict(code: str, message: str) -> CommerceError:
    return CommerceError(code, message)
