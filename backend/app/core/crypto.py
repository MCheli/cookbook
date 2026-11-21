"""Encrypt each user's own Anthropic key at rest (bring your own key).

The Fernet key is derived from COOKBOOK_SECRETS_KEY, so any long random string works there.
Keys are decrypted only in memory, right before a call to Anthropic, and never returned by the API.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(("cookbook-byok:" + settings.SECRETS_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
