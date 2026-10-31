"""Application errors translated at the HTTP boundary."""


class PassportError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def missing() -> PassportError:
    return PassportError("NOT_FOUND", "Resource not found.")


def conflict(
    code="REVISION_CONFLICT", message="Reload the draft and review its preview before retrying."
):
    return PassportError(code, message)
