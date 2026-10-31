"""Marketplace domain failures, independent of HTTP adapters."""


class ListingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def missing() -> ListingError:
    return ListingError("NOT_FOUND", "The requested resource was not found.")


def conflict(code="REVISION_CONFLICT", message="The listing revision has changed."):
    return ListingError(code, message)
