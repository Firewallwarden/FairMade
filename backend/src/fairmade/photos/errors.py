"""Private media failures are not cacheable and never echo upload details."""

from fastapi import HTTPException

from fairmade.auth import api_error


def photo_error(status: int, code: str, message: str) -> HTTPException:
    error = api_error(status, code, message)
    error.headers = {**(error.headers or {}), "Cache-Control": "no-store"}
    return error
