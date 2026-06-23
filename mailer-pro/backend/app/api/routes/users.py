from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, DB
from app.core.security import hash_password
from app.db.models.users import User

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "mailer"
    full_name: str | None = None


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


def user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "last_login": u.last_login,
    }


@router.get("")
async def list_users(db: DB, _: AdminUser):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [user_to_dict(u) for u in result.scalars().all()]


@router.post("", status_code=201)
async def create_user(body: CreateUserRequest, db: DB, _: AdminUser):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user_to_dict(user)


@router.put("/{user_id}")
async def update_user(user_id: int, body: UpdateUserRequest, db: DB, _: AdminUser):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    return user_to_dict(user)


@router.delete("/{user_id}")
async def deactivate_user(user_id: int, db: DB, _: AdminUser):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return {"detail": "User deactivated"}
