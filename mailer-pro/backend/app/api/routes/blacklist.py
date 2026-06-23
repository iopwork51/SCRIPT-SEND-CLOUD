from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.db.models.suppression import Blacklist, SuppressionEntry

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


class BlacklistCreate(BaseModel):
    email: str | None = None
    domain: str | None = None
    reason: str | None = None
    source: str = "manual"


class BulkBlacklistRequest(BaseModel):
    entries: list[str]  # emails or domains
    source: str = "import"
    reason: str | None = None


@router.get("")
async def list_blacklist(db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50):
    result = await db.execute(
        select(Blacklist).order_by(Blacklist.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    entries = result.scalars().all()
    return [
        {
            "id": e.id, "email": e.email, "domain": e.domain,
            "reason": e.reason, "source": e.source, "created_at": e.created_at,
        }
        for e in entries
    ]


@router.post("", status_code=201)
async def add_blacklist(body: BlacklistCreate, db: DB, current_user: CurrentUser):
    if not body.email and not body.domain:
        raise HTTPException(status_code=400, detail="Provide email or domain")
    entry = Blacklist(
        email=body.email.lower() if body.email else None,
        domain=body.domain.lower() if body.domain else None,
        reason=body.reason,
        source=body.source,
        added_by=current_user.id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": entry.id}


@router.post("/import")
async def bulk_import_blacklist(body: BulkBlacklistRequest, db: DB, current_user: CurrentUser):
    added = 0
    for entry_str in body.entries:
        entry_str = entry_str.strip().lower()
        if not entry_str:
            continue
        if "@" in entry_str:
            entry = Blacklist(email=entry_str, reason=body.reason, source=body.source, added_by=current_user.id)
        else:
            entry = Blacklist(domain=entry_str, reason=body.reason, source=body.source, added_by=current_user.id)
        db.add(entry)
        added += 1
    await db.commit()
    return {"added": added}


@router.delete("/{entry_id}")
async def delete_blacklist(entry_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Blacklist).where(Blacklist.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(entry)
    await db.commit()
    return {"detail": "Removed"}


# ── Suppression ───────────────────────────────────────────────────────────────

suppression_router = APIRouter(prefix="/suppression", tags=["suppression"])


class SuppressionImport(BaseModel):
    offer_id: int
    emails: list[str]
    source: str = "manual"


@suppression_router.get("")
async def list_suppression(
    db: DB, current_user: CurrentUser,
    offer_id: int | None = None,
    page: int = 1, page_size: int = 50,
):
    q = select(SuppressionEntry)
    if offer_id:
        q = q.where(SuppressionEntry.offer_id == offer_id)
    q = q.order_by(SuppressionEntry.imported_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    entries = result.scalars().all()
    return [{"id": e.id, "email": e.email, "offer_id": e.offer_id, "imported_at": e.imported_at} for e in entries]


@suppression_router.post("/import")
async def import_suppression(body: SuppressionImport, db: DB, current_user: CurrentUser):
    records = [
        SuppressionEntry(email=e.lower().strip(), offer_id=body.offer_id)
        for e in body.emails if e and "@" in e
    ]
    db.add_all(records)
    await db.commit()
    return {"added": len(records)}
