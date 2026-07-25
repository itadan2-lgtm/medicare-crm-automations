"""Authentication, password hashing, and event signing."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _prehash(password: str) -> bytes:
    """SHA-256 then base64 before bcrypt.

    bcrypt silently truncates at 72 bytes, which would make two long passwords
    sharing a 72-byte prefix interchangeable. Pre-hashing gives every password a
    fixed 44-byte representation and removes the length ceiling.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database — treat as a failed login, not a 500.
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "typ": "user",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_service_token(agent_name: str, allowed_tools: list[str]) -> str:
    """Token for an agent worker.

    `typ: service` is what keeps a worker out of the approval endpoints — a
    compromised agent must not be able to release its own human-approval hold.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": agent_name,
        "typ": "service",
        "tools": allowed_tools,
        "iat": now,
        "exp": now + timedelta(hours=12),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    claims = decode_token(token)
    if claims.get("typ") != "user":
        # Service tokens are deliberately not accepted on user endpoints.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User token required")

    email = claims.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


# --- Event signing ---------------------------------------------------------


def sign_payload(payload: str) -> str:
    settings = get_settings()
    digest = hmac.new(settings.jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"


def verify_signature(payload: str, signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign_payload(payload), signature)
