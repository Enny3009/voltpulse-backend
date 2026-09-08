from datetime import datetime, timedelta, timezone
import hmac
from typing import Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from app.core.config import settings

ph = PasswordHasher()


def hash_secret(secret: str) -> str:
    """Hashes passwords and device API keys using Argon2id."""
    return ph.hash(secret)


def verify_secret(hash_: str, secret: str) -> bool:
    """Verifies a secret against an Argon2id hash."""
    try:
        return ph.verify(hash_, secret)
    except VerifyMismatchError:
        return False


def verify_device_key_constant_time(stored_hash: str, incoming_key: str) -> bool:
    """
    Constant-time comparison for hardware device keys.
    Mitigates side-channel timing attacks.
    """
    try:
        return ph.verify(stored_hash, incoming_key)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Generates an expiring JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decodes and validates a JWT token signature and expiration."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])