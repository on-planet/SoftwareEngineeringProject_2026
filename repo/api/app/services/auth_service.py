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


def is_admin_account(raw_account: str) -> bool:
    return normalize_account(raw_account) == normalize_account(settings.auth_admin_account)


def _serialize_auth_user(user: AuthUser) -> dict:
    return {
        "id": int(user.id),
        "email": user.email,
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
        "is_admin": is_admin_account(user.email),
        "created_at": user.created_at,
    }


def _ensure_admin_user(db: Session) -> AuthUser:
    admin_account = normalize_account(settings.auth_admin_account)
    admin_password = settings.auth_admin_password
    user = db.query(AuthUser).filter(AuthUser.email == admin_account).first()
    if user is None:
        salt = generate_password_salt()
        user = AuthUser(
            email=admin_account,
            password_hash=hash_password(admin_password, salt),
            password_salt=salt,
            is_active=True,
            is_email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    changed = False
    if not verify_password(admin_password, user.password_salt, user.password_hash):
        salt = generate_password_salt()
        user.password_salt = salt
        user.password_hash = hash_password(admin_password, salt)
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True
    if not user.is_email_verified:
        user.is_email_verified = True
        changed = True
    if changed:
        db.commit()
        db.refresh(user)
    return user


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
        "user": _serialize_auth_user(user),
    }


def register_user(db: Session, *, account: str, password: str) -> dict:
    normalized_account = normalize_account(account)
    if is_admin_account(normalized_account):
        raise ValueError("The admin account is reserved")
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
    if is_admin_account(normalized_account):
        if password != settings.auth_admin_password:
            raise ValueError("Account or password is incorrect")
        user = _ensure_admin_user(db)
        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return _build_token_payload(user)

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
