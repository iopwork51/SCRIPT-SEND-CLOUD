from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete

from app.api.deps import CurrentUser, DB
from app.db.models.offers import Offer, OfferDataField
from app.db.models.affiliates import AffiliateNetwork
from app.db.models.suppression import SuppressionEntry

router = APIRouter(prefix="/offers", tags=["offers"])


class OfferCreate(BaseModel):
    name: str
    network_id: int | None = None
    external_id: str | None = None
    description: str | None = None
    tracking_url: str | None = None
    preview_url: str | None = None
    payout: float | None = None
    currency: str = "USD"
    suggested_subject: str | None = None
    suggested_from_name: str | None = None
    html_creative: str | None = None
    max_sends_per_day: int | None = None


class OfferUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tracking_url: str | None = None
    preview_url: str | None = None
    payout: float | None = None
    suggested_subject: str | None = None
    suggested_from_name: str | None = None
    html_creative: str | None = None
    is_active: bool | None = None
    max_sends_per_day: int | None = None


class ImportOffersRequest(BaseModel):
    network_id: int
    offer_ids: list[str] = []
    get_all: bool = False
    max_creatives: int = 1
    get_all_creatives: bool = False


class DataFieldCreate(BaseModel):
    field_key: str
    field_value: str | None = None
    data_type: str = "text"


def offer_to_dict(o: Offer) -> dict:
    return {
        "id": o.id,
        "network_id": o.network_id,
        "external_id": o.external_id,
        "name": o.name,
        "description": o.description,
        "tracking_url": o.tracking_url,
        "preview_url": o.preview_url,
        "payout": float(o.payout) if o.payout else None,
        "currency": o.currency,
        "suggested_subject": o.suggested_subject,
        "suggested_from_name": o.suggested_from_name,
        "is_active": o.is_active,
        "max_sends_per_day": o.max_sends_per_day,
        "created_at": o.created_at,
    }


@router.get("")
async def list_offers(
    db: DB, current_user: CurrentUser,
    network_id: int | None = None,
    page: int = 1, page_size: int = 50,
):
    q = select(Offer).where(Offer.is_active == True)
    if network_id:
        q = q.where(Offer.network_id == network_id)
    q = q.order_by(Offer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return [offer_to_dict(o) for o in result.scalars().all()]


@router.post("/import", status_code=201)
async def import_offers(body: ImportOffersRequest, db: DB, current_user: CurrentUser):
    from app.services.affiliate_apis import get_affiliate_client, normalize_offer

    result = await db.execute(select(AffiliateNetwork).where(AffiliateNetwork.id == body.network_id))
    network = result.scalar_one_or_none()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    client = get_affiliate_client(network)
    if client is None:
        raise HTTPException(status_code=400, detail="Network has no API platform configured")

    max_creatives = None if body.get_all_creatives else body.max_creatives

    if body.get_all:
        raw_offers = client.get_all_offers()
    else:
        if not body.offer_ids:
            raise HTTPException(status_code=400, detail="Provide offer_ids or set get_all=true")
        raw_offers = [client.get_offer_by_id(oid) for oid in body.offer_ids]

    saved = []
    for raw in raw_offers:
        normalized = normalize_offer(raw, network.api_platform)

        creatives = client.get_offer_creatives(normalized["external_id"], max_creatives or 1)
        html_creative = creatives[0].get("html_content", "") if creatives else None

        suppression_emails = client.get_suppression(normalized["external_id"])

        offer = Offer(
            network_id=body.network_id,
            external_id=normalized.get("external_id"),
            name=normalized.get("name", ""),
            description=normalized.get("description"),
            tracking_url=normalized.get("tracking_url"),
            preview_url=normalized.get("preview_url"),
            payout=normalized.get("payout"),
            currency=normalized.get("currency", "USD"),
            suggested_subject=normalized.get("suggested_subject"),
            suggested_from_name=normalized.get("suggested_from_name"),
            html_creative=html_creative,
        )
        db.add(offer)
        await db.flush()

        # Bulk insert suppression list
        if suppression_emails:
            db.add_all([
                SuppressionEntry(email=e.lower().strip(), offer_id=offer.id)
                for e in suppression_emails if e and "@" in e
            ])

        saved.append({"external_id": offer.external_id, "name": offer.name, "suppression_count": len(suppression_emails)})

    await db.commit()
    return {"imported": len(saved), "offers": saved}


@router.post("", status_code=201)
async def create_offer_manual(body: OfferCreate, db: DB, current_user: CurrentUser):
    offer = Offer(**body.model_dump())
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return offer_to_dict(offer)


@router.put("/{offer_id}")
async def update_offer(offer_id: int, body: OfferUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(offer, field, value)

    await db.commit()
    return offer_to_dict(offer)


@router.delete("/{offer_id}")
async def delete_offer(offer_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer.is_active = False
    await db.commit()
    return {"detail": "Deactivated"}


# ── Data Fields ──────────────────────────────────────────────────────────────

@router.get("/{offer_id}/data")
async def get_data_fields(offer_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(OfferDataField).where(OfferDataField.offer_id == offer_id))
    fields = result.scalars().all()
    return [{"id": f.id, "field_key": f.field_key, "field_value": f.field_value, "data_type": f.data_type} for f in fields]


@router.post("/{offer_id}/data", status_code=201)
async def add_data_field(offer_id: int, body: DataFieldCreate, db: DB, current_user: CurrentUser):
    field = OfferDataField(offer_id=offer_id, **body.model_dump())
    db.add(field)
    await db.commit()
    await db.refresh(field)
    return {"id": field.id, "field_key": field.field_key, "field_value": field.field_value}


@router.put("/{offer_id}/data/{field_id}")
async def update_data_field(offer_id: int, field_id: int, body: DataFieldCreate, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(OfferDataField).where(OfferDataField.id == field_id, OfferDataField.offer_id == offer_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    field.field_key = body.field_key
    field.field_value = body.field_value
    field.data_type = body.data_type
    await db.commit()
    return {"id": field.id, "field_key": field.field_key}


@router.delete("/{offer_id}/data/{field_id}")
async def delete_data_field(offer_id: int, field_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(OfferDataField).where(OfferDataField.id == field_id, OfferDataField.offer_id == offer_id)
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    await db.delete(field)
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{offer_id}/sync-suppression")
async def sync_suppression(offer_id: int, db: DB, current_user: CurrentUser):
    from app.services.affiliate_apis import get_affiliate_client

    result = await db.execute(select(Offer).where(Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    if not offer.network_id:
        raise HTTPException(status_code=400, detail="Offer has no affiliate network")

    net_result = await db.execute(select(AffiliateNetwork).where(AffiliateNetwork.id == offer.network_id))
    network = net_result.scalar_one_or_none()
    client = get_affiliate_client(network)
    if not client:
        raise HTTPException(status_code=400, detail="No API client for this network")

    await db.execute(delete(SuppressionEntry).where(SuppressionEntry.offer_id == offer_id))
    fresh = client.get_suppression(offer.external_id)
    db.add_all([
        SuppressionEntry(email=e.lower().strip(), offer_id=offer_id)
        for e in fresh if e and "@" in e
    ])
    await db.commit()
    return {"synced": len(fresh)}
