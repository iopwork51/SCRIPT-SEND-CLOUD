from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DB
from app.core.security import encrypt_secret, decrypt_secret
from app.db.models.accounts import SenderAccount, SenderGroup

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    email: str
    password: str
    account_type: str = "gmail"
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_user: str | None = None
    proxy_pass: str | None = None
    proxy_geo: str | None = None
    proxy_type: str = "webshare_gb"
    group_id: int | None = None
    max_per_day: int = 500


class AccountUpdate(BaseModel):
    account_type: str | None = None
    proxy_host: str | None = None
    proxy_port: int | None = None
    proxy_user: str | None = None
    proxy_pass: str | None = None
    proxy_geo: str | None = None
    proxy_type: str | None = None
    group_id: int | None = None
    max_per_day: int | None = None
    status: str | None = None


def account_to_dict(a: SenderAccount) -> dict:
    return {
        "id": a.id,
        "email": a.email,
        "account_type": a.account_type,
        "proxy_host": a.proxy_host,
        "proxy_port": a.proxy_port,
        "proxy_user": a.proxy_user,
        "proxy_geo": a.proxy_geo,
        "proxy_type": a.proxy_type,
        "group_id": a.group_id,
        "status": a.status,
        "last_health_check": a.last_health_check,
        "last_send": a.last_send,
        "total_sent": a.total_sent,
        "daily_sent": a.daily_sent,
        "max_per_day": a.max_per_day,
        "created_at": a.created_at,
    }


@router.get("")
async def list_accounts(
    db: DB,
    current_user: CurrentUser,
    group_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    query = select(SenderAccount).where(
        SenderAccount.is_deleted == False,
        SenderAccount.user_id == current_user.id if current_user.role != "admin" else True,
    )
    if group_id:
        query = query.where(SenderAccount.group_id == group_id)
    if status:
        query = query.where(SenderAccount.status == status)

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return [account_to_dict(a) for a in result.scalars().all()]


@router.post("", status_code=201)
async def create_account(body: AccountCreate, db: DB, current_user: CurrentUser):
    existing = await db.execute(select(SenderAccount).where(SenderAccount.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account already exists")

    account = SenderAccount(
        email=body.email,
        password=encrypt_secret(body.password),
        account_type=body.account_type,
        proxy_host=body.proxy_host,
        proxy_port=body.proxy_port,
        proxy_user=body.proxy_user,
        proxy_pass=encrypt_secret(body.proxy_pass) if body.proxy_pass else None,
        proxy_geo=body.proxy_geo,
        proxy_type=body.proxy_type,
        group_id=body.group_id,
        user_id=current_user.id,
        max_per_day=body.max_per_day,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account_to_dict(account)


@router.post("/bulk", status_code=201)
async def bulk_import_accounts(
    db: DB,
    current_user: CurrentUser,
    csv_data: str | None = None,
    file: UploadFile | None = None,
    group_id: int | None = None,
):
    """
    Import accounts from CSV.
    Short format (auto-assigns proxy from pool): email:password:geo
    Full format:                                 email:password:proxy_host:port:proxy_user:proxy_pass:geo:type
    """
    from app.services.proxy import get_proxy_from_pool

    if file:
        content = (await file.read()).decode("utf-8")
    elif csv_data:
        content = csv_data
    else:
        raise HTTPException(status_code=400, detail="Provide csv_data or file")

    lines = [l.strip() for l in content.splitlines() if l.strip()]
    created, skipped, errors = [], 0, []

    for line in lines:
        parts = line.split(":")
        if len(parts) < 2:
            errors.append(f"Invalid format: {line[:50]}")
            continue

        email = parts[0].strip()
        password = parts[1].strip()

        existing = await db.execute(select(SenderAccount).where(SenderAccount.email == email))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        if len(parts) == 3:
            # Short format: email:password:geo — auto-assign proxy from pool
            geo = parts[2].strip().upper()
            proxy = await get_proxy_from_pool(geo, db)
            account = SenderAccount(
                email=email,
                password=encrypt_secret(password),
                proxy_host=proxy["host"] if proxy else None,
                proxy_port=proxy["port"] if proxy else None,
                proxy_user=proxy["user"] if proxy else None,
                proxy_pass=encrypt_secret(proxy["pass"]) if proxy and proxy.get("pass") else None,
                proxy_geo=geo,
                proxy_type=proxy["type"] if proxy else "http",
                group_id=group_id,
                user_id=current_user.id,
            )
        elif len(parts) >= 8:
            # Full format: email:password:proxy_host:port:proxy_user:proxy_pass:geo:type
            proxy_host, proxy_port, proxy_user, proxy_pass, geo, ptype = parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
            account = SenderAccount(
                email=email,
                password=encrypt_secret(password),
                proxy_host=proxy_host,
                proxy_port=int(proxy_port),
                proxy_user=proxy_user,
                proxy_pass=encrypt_secret(proxy_pass),
                proxy_geo=geo.upper(),
                proxy_type=ptype,
                group_id=group_id,
                user_id=current_user.id,
            )
        else:
            errors.append(f"Invalid format (need 3 or 8+ fields): {line[:60]}")
            continue

        db.add(account)
        created.append(email)

    await db.commit()
    return {"created": len(created), "skipped": skipped, "errors": errors}


@router.put("/{account_id}")
async def update_account(account_id: int, body: AccountUpdate, db: DB, current_user: CurrentUser):
    result = await db.execute(
        select(SenderAccount).where(SenderAccount.id == account_id, SenderAccount.is_deleted == False)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.proxy_host is not None:
        account.proxy_host = body.proxy_host
    if body.proxy_port is not None:
        account.proxy_port = body.proxy_port
    if body.proxy_user is not None:
        account.proxy_user = body.proxy_user
    if body.proxy_pass is not None:
        account.proxy_pass = encrypt_secret(body.proxy_pass)
    if body.proxy_geo is not None:
        account.proxy_geo = body.proxy_geo
    if body.proxy_type is not None:
        account.proxy_type = body.proxy_type
    if body.group_id is not None:
        account.group_id = body.group_id
    if body.max_per_day is not None:
        account.max_per_day = body.max_per_day
    if body.status is not None:
        account.status = body.status

    await db.commit()
    return account_to_dict(account)


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: DB, current_user: CurrentUser):
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.is_deleted = True
    await db.commit()
    return {"detail": "Deleted"}


@router.post("/{account_id}/test")
async def test_account(account_id: int, db: DB, current_user: CurrentUser, background_tasks: BackgroundTasks):
    from app.services.proxy import full_account_health_check
    from datetime import datetime, timezone

    result = await db.execute(select(SenderAccount).where(SenderAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account_dict = {
        "email": account.email,
        "password": decrypt_secret(account.password),
        "proxy_host": account.proxy_host,
        "proxy_port": account.proxy_port,
        "proxy_user": account.proxy_user,
        "proxy_pass": decrypt_secret(account.proxy_pass) if account.proxy_pass else None,
        "proxy_geo": account.proxy_geo,
    }
    health = await full_account_health_check(account_dict)
    account.status = health["status"]
    account.last_health_check = datetime.now(timezone.utc)
    await db.commit()
    return health


@router.post("/test-all")
async def test_all_accounts(db: DB, current_user: CurrentUser, background_tasks: BackgroundTasks):
    from app.tasks.health_tasks import check_all_accounts
    background_tasks.add_task(check_all_accounts)
    return {"detail": "Health checks started in background"}


@router.post("/{account_id}/rotate-proxy")
async def rotate_proxy(account_id: int, db: DB, current_user: CurrentUser):
    from app.services.proxy import rotate_account_proxy

    result = await db.execute(select(SenderAccount).where(SenderAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result_data = await rotate_account_proxy(account_id, account.proxy_geo or "US", db)
    return result_data
