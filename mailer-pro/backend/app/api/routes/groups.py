from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from app.api.deps import CurrentUser, DB
from app.db.models.accounts import SenderGroup, SenderAccount

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("")
async def list_groups(db: DB, current_user: CurrentUser):
    result = await db.execute(select(SenderGroup).order_by(SenderGroup.created_at.desc()))
    groups = result.scalars().all()

    output = []
    for g in groups:
        count_result = await db.execute(
            select(func.count()).select_from(SenderAccount)
            .where(SenderAccount.group_id == g.id, SenderAccount.is_deleted == False)
        )
        total = count_result.scalar()
        active_result = await db.execute(
            select(func.count()).select_from(SenderAccount)
            .where(SenderAccount.group_id == g.id, SenderAccount.status == "active", SenderAccount.is_deleted == False)
        )
        active = active_result.scalar()
        output.append({
            "id": g.id, "name": g.name, "description": g.description,
            "total_accounts": total, "active_accounts": active,
            "created_at": g.created_at,
        })
    return output


@router.post("", status_code=201)
async def create_group(body: GroupCreate, db: DB, current_user: CurrentUser):
    group = SenderGroup(name=body.name, description=body.description, user_id=current_user.id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return {"id": group.id, "name": group.name, "description": group.description}


@router.put("/{group_id}")
async def update_group(group_id: int, body: GroupUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(SenderGroup).where(SenderGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if body.name is not None:
        group.name = body.name
    if body.description is not None:
        group.description = body.description
    await db.commit()
    return {"id": group.id, "name": group.name}


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(SenderGroup).where(SenderGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return {"detail": "Deleted"}


@router.get("/{group_id}/accounts")
async def get_group_accounts(group_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(SenderAccount)
        .where(SenderAccount.group_id == group_id, SenderAccount.is_deleted == False)
    )
    accounts = result.scalars().all()
    return [{"id": a.id, "email": a.email, "status": a.status, "proxy_geo": a.proxy_geo} for a in accounts]
