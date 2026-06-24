from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DB
from app.core.security import encrypt_secret, decrypt_secret
from app.db.models.proxies import ProxyProvider, Proxy

router = APIRouter(prefix="/proxy-providers", tags=["proxy-providers"])

COMMON_GEOS = ["US", "GB", "FR", "DE", "CA", "AU", "NL", "ES", "IT", "BR", "PL", "TR", "IN", "JP", "SG"]


class ProviderCreate(BaseModel):
    name: str                         # webshare | dataimpulse
    label: str
    api_key: str | None = None
    api_user: str | None = None
    api_pass: str | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None


class ProviderUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    api_user: str | None = None
    api_pass: str | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None
    is_active: bool | None = None


class DataImpulseSyncRequest(BaseModel):
    geos: list[str] = COMMON_GEOS


def provider_to_dict(p: ProxyProvider, proxy_count: int = 0) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "label": p.label,
        "api_user": p.api_user,
        "proxy_host": p.proxy_host,
        "proxy_port": p.proxy_port,
        "proxy_username": p.proxy_username,
        "is_active": p.is_active,
        "proxy_count": proxy_count,
        "created_at": p.created_at,
        # never return secrets
    }


@router.get("")
async def list_providers(db: DB, current_user: CurrentUser):
    result = await db.execute(select(ProxyProvider).where(ProxyProvider.is_active == True))
    providers = result.scalars().all()

    out = []
    for p in providers:
        count_result = await db.execute(
            select(Proxy).where(Proxy.provider_id == p.id, Proxy.is_deleted == False)
        )
        count = len(count_result.scalars().all())
        out.append(provider_to_dict(p, count))
    return out


@router.post("", status_code=201)
async def create_provider(body: ProviderCreate, db: DB, current_user: CurrentUser):
    if body.name not in ("webshare", "dataimpulse"):
        raise HTTPException(status_code=400, detail="name must be 'webshare' or 'dataimpulse'")

    provider = ProxyProvider(
        name=body.name,
        label=body.label,
        api_key=encrypt_secret(body.api_key) if body.api_key else None,
        api_user=body.api_user,
        api_pass=encrypt_secret(body.api_pass) if body.api_pass else None,
        proxy_host=body.proxy_host,
        proxy_port=body.proxy_port,
        proxy_username=body.proxy_username,
        proxy_password=encrypt_secret(body.proxy_password) if body.proxy_password else None,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider_to_dict(provider)


@router.put("/{provider_id}")
async def update_provider(provider_id: int, body: ProviderUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(ProxyProvider).where(ProxyProvider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.label is not None:
        p.label = body.label
    if body.api_key is not None:
        p.api_key = encrypt_secret(body.api_key)
    if body.api_user is not None:
        p.api_user = body.api_user
    if body.api_pass is not None:
        p.api_pass = encrypt_secret(body.api_pass)
    if body.proxy_host is not None:
        p.proxy_host = body.proxy_host
    if body.proxy_port is not None:
        p.proxy_port = body.proxy_port
    if body.proxy_username is not None:
        p.proxy_username = body.proxy_username
    if body.proxy_password is not None:
        p.proxy_password = encrypt_secret(body.proxy_password)
    if body.is_active is not None:
        p.is_active = body.is_active

    await db.commit()
    return provider_to_dict(p)


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(ProxyProvider).where(ProxyProvider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(p)
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{provider_id}/sync")
async def sync_proxies(
    provider_id: int,
    db: DB,
    current_user: CurrentUser,
    body: DataImpulseSyncRequest | None = None,
):
    result = await db.execute(select(ProxyProvider).where(ProxyProvider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")

    api_key = decrypt_secret(p.api_key) if p.api_key else None

    if p.name == "webshare":
        if not api_key:
            raise HTTPException(status_code=400, detail="Webshare API key not set")
        from app.services.proxy import webshare_sync_to_db
        stats = await webshare_sync_to_db(provider_id, api_key, db)

    elif p.name == "dataimpulse":
        if not p.proxy_host or not p.proxy_username:
            raise HTTPException(status_code=400, detail="DataImpulse proxy host and username required")
        proxy_password = decrypt_secret(p.proxy_password) if p.proxy_password else ""
        geos = (body.geos if body and body.geos else None) or COMMON_GEOS
        from app.services.proxy import dataimpulse_sync_to_db
        stats = await dataimpulse_sync_to_db(
            provider_id, p.proxy_host, p.proxy_port or 823,
            p.proxy_username, proxy_password, geos, db,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {p.name}")

    return {"provider": p.name, **stats}


@router.get("/{provider_id}/usage")
async def get_usage(provider_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(ProxyProvider).where(ProxyProvider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")

    api_key = decrypt_secret(p.api_key) if p.api_key else None

    try:
        if p.name == "webshare":
            if not api_key:
                raise HTTPException(status_code=400, detail="Webshare API key not set")
            from app.services.proxy import webshare_get_usage
            return await webshare_get_usage(api_key)
        elif p.name == "dataimpulse":
            if not api_key:
                raise HTTPException(status_code=400, detail="DataImpulse API key not set")
            from app.services.proxy import dataimpulse_get_usage
            return await dataimpulse_get_usage(api_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Provider API error: {e}")
