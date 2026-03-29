from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.auth import AuthTokenOut, AuthUserOut, LoginIn, RegisterIn
from app.services.auth_service import _serialize_auth_user, get_user_from_token, login_user, register_user

router = APIRouter(tags=["auth"])
http_bearer = HTTPBearer(auto_error=False)


@router.post("/auth/register", response_model=AuthTokenOut)
def register_route(payload: RegisterIn, db: Session = Depends(get_db)):
    account = (payload.account or "").strip()
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing account")
    try:
        return register_user(db, account=account, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/auth/login", response_model=AuthTokenOut)
def login_route(payload: LoginIn, db: Session = Depends(get_db)):
    account = (payload.account or "").strip()
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing account")
    try:
        return login_user(db, account=account, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        return get_user_from_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.get("/auth/me", response_model=AuthUserOut)
def me_route(current_user=Depends(get_current_user)):
    return _serialize_auth_user(current_user)
