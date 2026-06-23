from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
import secrets

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, hash_password
from app.db.models.users import User, UserSession
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
DB = Annotated[AsyncSession, Depends(get_db)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DB):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(UserSession(user_id=user.id, refresh_token=refresh_token, expires_at=expires))

    # Update last login
    await db.execute(
        update(User).where(User.id == user.id).values(last_login=datetime.utcnow())
    )
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: DB):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(
        select(UserSession).where(UserSession.refresh_token == body.refresh_token)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")

    if session.expires_at and session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    result2 = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result2.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")

    new_access = create_access_token(user.id, user.role)
    new_refresh = create_refresh_token(user.id)

    session.refresh_token = new_refresh
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session.expires_at = expires
    await db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
    db: DB,
    refresh_token: str | None = None,
):
    if refresh_token:
        result = await db.execute(
            select(UserSession).where(UserSession.refresh_token == refresh_token)
        )
        session = result.scalar_one_or_none()
        if session:
            await db.delete(session)
            await db.commit()
    return {"detail": "Logged out"}


@router.get("/me")
async def me(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
    db: DB,
):
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role}
