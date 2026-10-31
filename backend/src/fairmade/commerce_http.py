"""HTTP error adapter shared by inventory and orders."""

from fastapi import Request
from fastapi.responses import JSONResponse

from fairmade.commerce_errors import CommerceError


async def commerce_error_handler(_request: Request, exc: CommerceError) -> JSONResponse:
    return JSONResponse(
        status_code=404 if exc.code == "NOT_FOUND" else 409,
        content={"detail": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )
