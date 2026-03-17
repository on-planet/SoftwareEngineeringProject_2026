from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, generate_password_salt, hash_password, verify_password
from app.models.auth_user import AuthUser

ACCOUNT_PATTERN = re.compile(r"^[^\s]{3,64}$")


def normalize_account(raw_account: str) -> str:
    account = (raw_account or "").strip().lower()
    if not ACCOUNT_PATTERN.fullmatch(account):
        raise ValueError("Invalid account format: use 3-64 non-space characters")
    return account


def _build_token_payload(user: AuthUser) -> dict:
    expires_in_seconds = int(settings.auth_token_expire_hours) * 3600
    return {
        "access_token": create_access_token(
            user_id=int(user.id),
            email=user.email,
            expires_in_seconds=expires_in_seconds,
        ),
        "token_type": "bearer",
        "expires_in_seconds": expires_in_seconds,
        "user": user,
    }


def register_user(db: Session, *, account: str, password: str) -> dict:
    normalized_account = normalize_account(account)
    existing_user = db.query(AuthUser).filter(AuthUser.email == normalized_account).first()
    if existing_user is not None:
        raise ValueError("Account already exists")

    salt = generate_password_salt()
    user = AuthUser(
        email=normalized_account,
        password_hash=hash_password(password, salt),
        password_salt=salt,
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_token_payload(user)


def login_user(db: Session, *, account: str, password: str) -> dict:
    normalized_account = normalize_account(account)
    user = db.query(AuthUser).filter(AuthUser.email == normalized_account).first()
    if user is None:
        raise ValueError("Account or password is incorrect")
    if not user.is_active:
        raise ValueError("Account is disabled")
    if not verify_password(password, user.password_salt, user.password_hash):
        raise ValueError("Account or password is incorrect")

    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return _build_token_payload(user)


def get_user_from_token(db: Session, token: str) -> AuthUser:
    payload = decode_access_token(token)
    user_id = int(payload.get("sub") or 0)
    if user_id <= 0:
        raise ValueError("Invalid token payload")
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if user is None or not user.is_active:
        raise ValueError("User not found")
    return user
