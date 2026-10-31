"""Explicit server-only credentials; production URLs/mode are not supported."""

import os
import re
from dataclasses import dataclass

from pydantic import SecretStr


@dataclass(frozen=True)
class SandboxSettings:
    client_id: str
    client_secret: SecretStr
    merchant_id: str


def load_settings() -> SandboxSettings | None:
    enabled = os.environ.get("FAIRMADE_PAYPAL_ENABLED", "false")
    if enabled not in ("true", "false"):
        raise ValueError("FAIRMADE_PAYPAL_ENABLED must be true or false")
    if enabled == "false":
        return None
    if os.environ.get("FAIRMADE_PAYPAL_ENVIRONMENT", "sandbox") != "sandbox":
        raise ValueError("Only the PayPal sandbox environment is supported")
    client_id = os.environ.get("FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID", "").strip()
    secret = os.environ.get("FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET", "").strip()
    merchant_id = os.environ.get("FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID", "").strip()
    if not client_id or not secret or not re.fullmatch(r"[A-Z0-9]{13}", merchant_id):
        raise ValueError("Configure sandbox client credentials and the 13-character merchant ID")
    return SandboxSettings(client_id, SecretStr(secret), merchant_id)
