from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.db.models.affiliates import AffiliateNetwork

router = APIRouter(prefix="/affiliates", tags=["affiliates"])


class NetworkCreate(BaseModel):
    affiliate_id: str | None = None
    name: str
    status: str = "activated"
    website_url: str | None = None
    username: str | None = None
    password: str | None = None
    api_platform: str = "none"
    network_id: str | None = None
    company_name: str | None = None
    api_key: str | None = None
    api_username: str | None = None
    api_password: str | None = None
    sub_config: dict = {}


class NetworkUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    website_url: str | None = None
    username: str | None = None
    password: str | None = None
    api_platform: str | None = None
    network_id: str | None = None
    company_name: str | None = None
    api_key: str | None = None
    api_username: str | None = None
    api_password: str | None = None
    sub_config: dict | None = None


def network_to_dict(n: AffiliateNetwork) -> dict:
    return {
        "id": n.id,
        "affiliate_id": n.affiliate_id,
        "name": n.name,
        "status": n.status,
        "website_url": n.website_url,
        "username": n.username,
        "api_platform": n.api_platform,
        "network_id": n.network_id,
        "company_name": n.company_name,
        "api_key": n.api_key,
        "api_username": n.api_username,
        "sub_config": n.sub_config,
        "created_at": n.created_at,
    }


@router.get("")
async def list_networks(db: DB, current_user: CurrentUser, page: int = 1, page_size: int = 50):
    result = await db.execute(
        select(AffiliateNetwork).order_by(AffiliateNetwork.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    return [network_to_dict(n) for n in result.scalars().all()]


@router.post("", status_code=201)
async def create_network(body: NetworkCreate, db: DB, current_user: CurrentUser):
    network = AffiliateNetwork(
        affiliate_id=body.affiliate_id,
        name=body.name,
        status=body.status,
        website_url=body.website_url,
        username=body.username,
        password=body.password,
        api_platform=body.api_platform,
        network_id=body.network_id,
        company_name=body.company_name,
        api_key=body.api_key,
        api_username=body.api_username,
        api_password=body.api_password,
        sub_config=body.sub_config,
        user_id=current_user.id,
    )
    db.add(network)
    await db.commit()
    await db.refresh(network)
    return network_to_dict(network)


@router.put("/{network_id}")
async def update_network(network_id: int, body: NetworkUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(AffiliateNetwork).where(AffiliateNetwork.id == network_id))
    network = result.scalar_one_or_none()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(network, field, value)

    await db.commit()
    return network_to_dict(network)


@router.delete("/{network_id}")
async def delete_network(network_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(AffiliateNetwork).where(AffiliateNetwork.id == network_id))
    network = result.scalar_one_or_none()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    await db.delete(network)
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{network_id}/test")
async def test_network_api(network_id: int, db: DB, current_user: CurrentUser):
    from app.services.affiliate_apis import get_affiliate_client

    result = await db.execute(select(AffiliateNetwork).where(AffiliateNetwork.id == network_id))
    network = result.scalar_one_or_none()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    client = get_affiliate_client(network)
    if client is None:
        return {"success": False, "error": "No API platform configured"}

    try:
        offers = client.get_all_offers()
        return {"success": True, "offer_count": len(offers)}
    except Exception as e:
        return {"success": False, "error": str(e)}
