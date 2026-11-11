"""Password authentication and fixed-lifetime, server-revocable sessions."""

import hashlib
import secrets
from datetime import UTC, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fairmade.database import get_db, utcnow
from fairmade.models import Account, AccountRole, LoginSession
from fairmade.schemas import AccountResponse, Credentials, ErrorResponse, TokenResponse

router = APIRouter(prefix="/api/v1/auth", tags=["accounts"])
DB = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)
hasher = PasswordHasher()
_dummy_hash = hasher.hash(secrets.token_urlsafe(32))


def api_error(status: int, code: str, message: str) -> HTTPException:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return HTTPException(status, detail={"code": code, "message": message}, headers=headers)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def require_live_session(db: Session, token_hash: str, account_id: str) -> LoginSession:
    """Revalidate account/session after a long external operation."""
    db.expire_all()
    session = db.get(LoginSession, token_hash)
    if (
        session is None
        or session.account_id != account_id
        or session.expires_at.replace(tzinfo=UTC) <= utcnow()
    ):
        raise api_error(401, "UNAUTHORIZED", "A valid bearer token is required.")
    return session


def current_session(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> LoginSession:
    session = db.get(LoginSession, hash_token(credentials.credentials)) if credentials else None
    if session is None or session.expires_at.replace(tzinfo=UTC) <= utcnow():
        raise api_error(401, "UNAUTHORIZED", "A valid bearer token is required.")
    return session


Authenticated = Annotated[LoginSession, Depends(current_session)]
AUTH_ERRORS = {401: {"model": ErrorResponse}}


def current_account(auth: Authenticated, db: DB) -> Account:
    account = db.get(Account, auth.account_id)
    if account is None:
        raise api_error(401, "UNAUTHORIZED", "A valid bearer token is required.")
    return account


CurrentAccount = Annotated[Account, Depends(current_account)]


def require_seller(account: CurrentAccount) -> Account:
    if "seller" not in account.roles:
        raise api_error(403, "SELLER_REQUIRED", "Verified seller access is required.")
    return account


VerifiedSeller = Annotated[Account, Depends(require_seller)]


def require_admin(account: CurrentAccount) -> Account:
    if "admin" not in account.roles:
        raise api_error(403, "ADMIN_REQUIRED", "Administrator access is required.")
    return account


Administrator = Annotated[Account, Depends(require_admin)]


@router.post(
    "/register",
    response_model=AccountResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
)
def register(body: Credentials, db: DB) -> Account:
    account = Account(
        email=str(body.email),
        password_hash=hasher.hash(body.password.get_secret_value()),
        role_grants=[AccountRole(role="buyer")],
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise api_error(409, "EMAIL_EXISTS", "An account with this email already exists.") from None
    return account


@router.post("/login", response_model=TokenResponse, responses=AUTH_ERRORS)
def login(body: Credentials, db: DB, response: Response) -> TokenResponse:
    response.headers["Cache-Control"] = "no-store"
    account = db.scalar(select(Account).where(Account.email == str(body.email)))
    try:
        hasher.verify(
            account.password_hash if account else _dummy_hash, body.password.get_secret_value()
        )
    except (VerificationError, InvalidHashError):
        raise api_error(401, "INVALID_CREDENTIALS", "Invalid email or password.") from None
    if account is None:
        raise api_error(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    if hasher.check_needs_rehash(account.password_hash):
        account.password_hash = hasher.hash(body.password.get_secret_value())
    token = secrets.token_urlsafe(32)
    now = utcnow()
    expires_at = now + timedelta(hours=24)
    db.add(
        LoginSession(
            token_hash=hash_token(token),
            account_id=account.id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    db.commit()
    return TokenResponse(access_token=token, expires_at=expires_at)


@router.post("/logout", status_code=204, responses=AUTH_ERRORS)
def logout(auth: Authenticated, db: DB) -> Response:
    db.delete(auth)
    db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=AccountResponse, responses=AUTH_ERRORS)
def me(account: CurrentAccount) -> Account:
    return account
