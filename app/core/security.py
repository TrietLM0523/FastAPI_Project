from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Convert a plaintext password into a secure hash."""
    return password_hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Check whether a plaintext password matches a stored hash."""
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": subject,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    subject = payload.get("sub")

    if not isinstance(subject, str) or not subject:
        raise jwt.InvalidTokenError("Token subject is missing")

    return subject
