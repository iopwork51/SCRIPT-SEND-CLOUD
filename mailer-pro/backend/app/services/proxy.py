import httpx
import socks
import smtplib
from typing import Optional
from datetime import datetime, timezone
from app.core.config import settings

WEBSHARE_BASE = "https://proxy.webshare.io/api/v2"
DATAIMPULSE_BASE = "https://api.dataimpulse.com"
DATAIMPULSE_PROXY_HOST = "gw.dataimpulse.com"
DATAIMPULSE_HTTP_PORT = 823
DATAIMPULSE_SOCKS5_PORT = 2334


# ── Webshare ──────────────────────────────────────────────────────────────────

async def webshare_get_usage(api_key: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/profile/",
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "used_gb": round(data.get("bandwidth_used", 0) / (1024 ** 3), 3),
            "total_gb": round(data.get("bandwidth_limit", 0) / (1024 ** 3), 3),
            "proxy_count": data.get("proxy_count", 0),
        }


async def webshare_fetch_proxies(api_key: str, page_size: int = 500) -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/proxy/list/",
            headers={"Authorization": f"Token {api_key}"},
            params={"mode": "direct", "valid": True, "page": 1, "page_size": page_size},
            timeout=20,
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def webshare_sync_to_db(provider_id: int, api_key: str, db) -> dict:
    from app.db.models.proxies import Proxy
    from app.core.security import encrypt_secret
    from sqlalchemy import select

    raw = await webshare_fetch_proxies(api_key)
    created = 0
    updated = 0

    for p in raw:
        host = p.get("proxy_address", "")
        port = p.get("ports", {}).get("socks5") or p.get("ports", {}).get("http")
        if not host or not port:
            continue

        geo = (p.get("country_code") or "").upper()
        username = p.get("username", "")
        password = p.get("password", "")

        result = await db.execute(
            select(Proxy).where(Proxy.host == host, Proxy.port == port, Proxy.is_deleted == False)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.username = username
            existing.password = encrypt_secret(password) if password else None
            existing.geo = geo
            updated += 1
        else:
            db.add(Proxy(
                provider_id=provider_id,
                host=host,
                port=int(port),
                username=username,
                password=encrypt_secret(password) if password else None,
                geo=geo,
                proxy_type="socks5",
                is_rotating=False,
            ))
            created += 1

    await db.commit()
    return {"created": created, "updated": updated, "total_fetched": len(raw)}


# ── DataImpulse ───────────────────────────────────────────────────────────────

async def dataimpulse_get_usage(api_key: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{DATAIMPULSE_BASE}/user/profile",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        traffic = data.get("traffic", {})
        return {
            "used_gb": round(traffic.get("used", 0) / (1024 ** 3), 3),
            "total_gb": round(traffic.get("total", 0) / (1024 ** 3), 3),
            "proxy_count": data.get("proxy_count", 0),
            "plan": data.get("plan", ""),
        }


async def dataimpulse_sync_to_db(
    provider_id: int,
    proxy_host: str,
    proxy_port: int,
    proxy_username: str,
    proxy_password: str,
    geos: list[str],
    db,
) -> dict:
    """
    DataImpulse uses rotating proxies — one gateway endpoint per geo.
    Username format: username-cc-US (geo-targeted rotating).
    """
    from app.db.models.proxies import Proxy
    from app.core.security import encrypt_secret
    from sqlalchemy import select

    created = 0
    updated = 0

    for geo in geos:
        geo = geo.upper().strip()
        if not geo:
            continue

        # Build geo-targeted username
        geo_username = f"{proxy_username}-cc-{geo}"
        host = proxy_host or DATAIMPULSE_PROXY_HOST
        port = proxy_port or DATAIMPULSE_HTTP_PORT

        result = await db.execute(
            select(Proxy).where(
                Proxy.provider_id == provider_id,
                Proxy.geo == geo,
                Proxy.is_deleted == False,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.host = host
            existing.port = port
            existing.username = geo_username
            existing.password = encrypt_secret(proxy_password) if proxy_password else None
            updated += 1
        else:
            db.add(Proxy(
                provider_id=provider_id,
                host=host,
                port=port,
                username=geo_username,
                password=encrypt_secret(proxy_password) if proxy_password else None,
                geo=geo,
                proxy_type="http",
                is_rotating=True,
            ))
            created += 1

    await db.commit()
    return {"created": created, "updated": updated, "geos": geos}


# ── Proxy pool helpers ────────────────────────────────────────────────────────

async def get_proxy_from_pool(geo: str, db) -> Optional[dict]:
    """Pick a working proxy for the given geo from the local pool."""
    from app.db.models.proxies import Proxy
    from app.core.security import decrypt_secret
    from sqlalchemy import select

    geo = geo.upper()
    result = await db.execute(
        select(Proxy)
        .where(Proxy.geo == geo, Proxy.status != "failed", Proxy.is_deleted == False)
        .order_by(Proxy.last_tested.desc().nullslast())
        .limit(1)
    )
    p = result.scalar_one_or_none()
    if not p:
        return None
    return {
        "host": p.host,
        "port": p.port,
        "user": p.username,
        "pass": decrypt_secret(p.password) if p.password else None,
        "geo": p.geo,
        "type": p.proxy_type,
    }


# ── Proxy connectivity test ───────────────────────────────────────────────────

async def _tcp_check(host: str, port: int, timeout: float = 6.0) -> bool:
    """TCP-only check — connects directly to the proxy gateway, uses ZERO proxy GB."""
    import asyncio
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, int(port)), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def test_proxy_connection(proxy: dict) -> dict:
    """
    Checks proxy reachability via TCP only (no HTTP through the proxy).
    This uses ZERO proxy bandwidth — just a raw TCP handshake to the proxy host.
    """
    host = proxy.get("host")
    port = proxy.get("port")
    if not host or not port:
        return {"working": False, "error": "Missing host or port"}

    ok = await _tcp_check(host, int(port))
    return {
        "working": ok,
        "error": None if ok else "TCP connect failed — proxy unreachable",
        "exit_ip": None,   # not fetched (saves GB)
        "exit_geo": None,
        "geo_matches": None,
    }


async def test_proxy_by_id(proxy_id: int, db) -> dict:
    """TCP-only test — zero proxy GB consumed."""
    from app.db.models.proxies import Proxy
    from sqlalchemy import select

    result = await db.execute(select(Proxy).where(Proxy.id == proxy_id))
    p = result.scalar_one_or_none()
    if not p:
        return {"working": False, "error": "Proxy not found"}

    ok = await _tcp_check(p.host, p.port)
    p.last_tested = datetime.now(timezone.utc)
    p.status = "active" if ok else "failed"
    await db.commit()

    return {"working": ok, "error": None if ok else "TCP connect failed"}


# ── SMTP test via proxy ───────────────────────────────────────────────────────

async def test_smtp_via_proxy(account_email: str, account_password: str, proxy: dict) -> dict:
    try:
        proxy_sock = socks.socksocket()
        proxy_sock.set_proxy(
            socks.SOCKS5,
            proxy["host"],
            int(proxy["port"]),
            username=proxy.get("user"),
            password=proxy.get("pass"),
        )
        proxy_sock.settimeout(15)
        proxy_sock.connect(("smtp.gmail.com", 587))

        smtp = smtplib.SMTP()
        smtp.sock = proxy_sock
        smtp.file = smtp.sock.makefile("rb")
        smtp._get_reply()
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(account_email, account_password)
        smtp.quit()

        return {"working": True, "smtp": "authenticated", "error": None}

    except smtplib.SMTPAuthenticationError:
        return {"working": False, "smtp": "auth_failed", "error": "Wrong password or App Password expired"}
    except smtplib.SMTPException as e:
        return {"working": False, "smtp": "smtp_error", "error": str(e)}
    except socks.ProxyError as e:
        return {"working": False, "smtp": "proxy_error", "error": f"Proxy failed: {e}"}
    except Exception as e:
        return {"working": False, "smtp": "connection_error", "error": str(e)}


async def full_account_health_check(account: dict) -> dict:
    proxy = {
        "host": account.get("proxy_host"),
        "port": account.get("proxy_port"),
        "user": account.get("proxy_user"),
        "pass": account.get("proxy_pass"),
        "geo": account.get("proxy_geo", ""),
        "type": account.get("proxy_type", "socks5"),
    }

    if not proxy["host"]:
        return {
            "status": "proxy_error",
            "proxy": {"working": False, "error": "No proxy configured"},
            "smtp": None,
            "recommended_action": "add_proxy",
        }

    proxy_result = await test_proxy_connection(proxy)
    if not proxy_result["working"]:
        return {"status": "proxy_error", "proxy": proxy_result, "smtp": None, "recommended_action": "rotate_proxy"}

    smtp_result = await test_smtp_via_proxy(account["email"], account["password"], proxy)
    if not smtp_result["working"]:
        status = "smtp_blocked" if smtp_result.get("smtp") == "smtp_error" else "auth_failed"
        return {
            "status": status,
            "proxy": proxy_result,
            "smtp": smtp_result,
            "recommended_action": "check_account" if status == "auth_failed" else "wait_retry",
        }

    return {"status": "active", "proxy": proxy_result, "smtp": smtp_result, "recommended_action": "none"}


async def rotate_account_proxy(account_id: int, geo: str, db) -> dict:
    from app.db.models.accounts import SenderAccount
    from app.core.security import encrypt_secret
    from sqlalchemy import select

    new_proxy = await get_proxy_from_pool(geo, db)
    if not new_proxy:
        return {"success": False, "error": f"No proxies available for geo: {geo}"}

    test = await test_proxy_connection(new_proxy)
    if not test["working"]:
        return {"success": False, "error": "Proxy from pool also failed health check"}

    result = await db.execute(select(SenderAccount).where(SenderAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        return {"success": False, "error": "Account not found"}

    account.proxy_host = new_proxy["host"]
    account.proxy_port = new_proxy["port"]
    account.proxy_user = new_proxy["user"]
    account.proxy_pass = encrypt_secret(new_proxy["pass"]) if new_proxy["pass"] else None
    account.proxy_geo = new_proxy["geo"]
    account.proxy_type = new_proxy["type"]
    account.status = "active"
    await db.commit()

    return {"success": True, "new_proxy": {k: v for k, v in new_proxy.items() if k != "pass"}, "test": test}
