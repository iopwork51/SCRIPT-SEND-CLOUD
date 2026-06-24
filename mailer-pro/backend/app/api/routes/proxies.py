from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from datetime import datetime, timezone

from app.api.deps import CurrentUser, DB
from app.core.security import encrypt_secret, decrypt_secret
from app.db.models.proxies import Proxy

router = APIRouter(prefix="/proxies", tags=["proxies"])


class ProxyCreate(BaseModel):
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    geo: str | None = None
    proxy_type: str = "http"   # http | socks5
    is_rotating: bool = False
    provider_id: int | None = None


class ProxyUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    geo: str | None = None
    proxy_type: str | None = None
    is_rotating: bool | None = None
    status: str | None = None


def proxy_to_dict(p: Proxy) -> dict:
    return {
        "id": p.id,
        "provider_id": p.provider_id,
        "host": p.host,
        "port": p.port,
        "username": p.username,
        "geo": p.geo,
        "proxy_type": p.proxy_type,
        "is_rotating": p.is_rotating,
        "status": p.status,
        "last_tested": p.last_tested,
        "exit_ip": p.exit_ip,
        "created_at": p.created_at,
    }


@router.get("")
async def list_proxies(
    db: DB,
    current_user: CurrentUser,
    geo: str | None = None,
    status: str | None = None,
    provider_id: int | None = None,
    page: int = 1,
    page_size: int = 100,
):
    query = select(Proxy).where(Proxy.is_deleted == False)
    if geo:
        query = query.where(Proxy.geo == geo.upper())
    if status:
        query = query.where(Proxy.status == status)
    if provider_id:
        query = query.where(Proxy.provider_id == provider_id)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [proxy_to_dict(p) for p in result.scalars().all()]


@router.post("", status_code=201)
async def create_proxy(body: ProxyCreate, db: DB, current_user: CurrentUser):
    p = Proxy(
        provider_id=body.provider_id,
        host=body.host,
        port=body.port,
        username=body.username,
        password=encrypt_secret(body.password) if body.password else None,
        geo=body.geo.upper() if body.geo else None,
        proxy_type=body.proxy_type,
        is_rotating=body.is_rotating,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return proxy_to_dict(p)


@router.put("/{proxy_id}")
async def update_proxy(proxy_id: int, body: ProxyUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id, Proxy.is_deleted == False))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Proxy not found")

    if body.host is not None:
        p.host = body.host
    if body.port is not None:
        p.port = body.port
    if body.username is not None:
        p.username = body.username
    if body.password is not None:
        p.password = encrypt_secret(body.password)
    if body.geo is not None:
        p.geo = body.geo.upper()
    if body.proxy_type is not None:
        p.proxy_type = body.proxy_type
    if body.is_rotating is not None:
        p.is_rotating = body.is_rotating
    if body.status is not None:
        p.status = body.status

    await db.commit()
    return proxy_to_dict(p)


@router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Proxy not found")
    p.is_deleted = True
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{proxy_id}/test")
async def test_proxy(proxy_id: int, db: DB, current_user: CurrentUser):
    from app.services.proxy import test_proxy_by_id
    return await test_proxy_by_id(proxy_id, db)


@router.post("/test-all")
async def test_all_proxies(db: DB, current_user: CurrentUser):
    from app.services.proxy import test_proxy_by_id

    result = await db.execute(select(Proxy).where(Proxy.is_deleted == False))
    proxies = result.scalars().all()

    results = []
    for p in proxies:
        r = await test_proxy_by_id(p.id, db)
        results.append({"id": p.id, "geo": p.geo, **r})

    return {
        "tested": len(results),
        "active": sum(1 for r in results if r.get("working")),
        "failed": sum(1 for r in results if not r.get("working")),
    }
