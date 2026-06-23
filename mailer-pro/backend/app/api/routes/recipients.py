from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, delete

from app.api.deps import CurrentUser, DB
from app.db.models.recipients import RecipientList, Recipient

router = APIRouter(prefix="/recipients", tags=["recipients"])


class ListCreate(BaseModel):
    name: str
    description: str | None = None


@router.get("/lists")
async def list_recipient_lists(db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50):
    q = select(RecipientList)
    if current_user.role != "admin":
        q = q.where(RecipientList.user_id == current_user.id)
    q = q.order_by(RecipientList.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    lists = result.scalars().all()
    return [
        {
            "id": l.id, "name": l.name, "description": l.description,
            "total_count": l.total_count, "active_count": l.active_count,
            "created_at": l.created_at,
        }
        for l in lists
    ]


@router.post("/lists", status_code=201)
async def create_recipient_list(body: ListCreate, db: DB, current_user: CurrentUser):
    lst = RecipientList(name=body.name, description=body.description, user_id=current_user.id)
    db.add(lst)
    await db.commit()
    await db.refresh(lst)
    return {"id": lst.id, "name": lst.name}


@router.post("/lists/{list_id}/upload")
async def upload_recipients(list_id: int, db: DB, current_user: CurrentUser, file: UploadFile = File(...)):
    result = await db.execute(select(RecipientList).where(RecipientList.id == list_id))
    lst = result.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    content = (await file.read()).decode("utf-8", errors="ignore")
    lines = [l.strip() for l in content.splitlines() if l.strip()]

    added = 0
    for line in lines:
        # Support "email,name" or "email name" or just "email"
        parts = line.replace(",", " ").split()
        email = parts[0].lower()
        name = parts[1] if len(parts) > 1 else None

        if "@" not in email:
            continue

        db.add(Recipient(email=email, name=name, list_id=list_id))
        added += 1

    lst.total_count += added
    lst.active_count += added
    await db.commit()
    return {"added": added, "total": lst.total_count}


@router.delete("/lists/{list_id}")
async def delete_list(list_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(RecipientList).where(RecipientList.id == list_id))
    lst = result.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    await db.delete(lst)
    await db.commit()
    return {"detail": "Deleted"}


@router.get("/lists/{list_id}/count")
async def list_stats(list_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(RecipientList).where(RecipientList.id == list_id))
    lst = result.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    active_count = await db.execute(
        select(func.count()).select_from(Recipient)
        .where(Recipient.list_id == list_id, Recipient.status == "active")
    )
    return {
        "total": lst.total_count,
        "active": active_count.scalar(),
        "name": lst.name,
    }


@router.get("/lists/{list_id}/items")
async def get_list_recipients(
    list_id: int, db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50
):
    q = (
        select(Recipient)
        .where(Recipient.list_id == list_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return [{"id": r.id, "email": r.email, "name": r.name, "status": r.status} for r in result.scalars().all()]
