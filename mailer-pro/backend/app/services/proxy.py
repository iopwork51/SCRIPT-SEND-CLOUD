import httpx
import socks
import smtplib
from typing import Optional
from app.core.config import settings

WEBSHARE_BASE = "https://proxy.webshare.io/api/v2"


async def get_proxy_list(geo: str = None, page_size: int = 100) -> list:
    params = {"mode": "direct", "valid": True, "page": 1, "page_size": page_size}
    if geo:
        params["country_code__in"] = geo.upper()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/proxy/list/",
            headers={"Authorization": f"Token {settings.WEBSHARE_API_KEY}"},
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def get_fresh_proxy(geo: str = "US") -> Optional[dict]:
    proxies = await get_proxy_list(geo=geo, page_size=1)
    if not proxies:
        return None
    p = proxies[0]
    return {
        "host": p["proxy_address"],
        "port": p["ports"]["socks5"],
        "user": p["username"],
        "pass": p["password"],
        "geo": p["country_code"],
        "type": "socks5",
    }


async def get_proxy_usage() -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/profile/",
            headers={"Authorization": f"Token {settings.WEBSHARE_API_KEY}"},
            timeout=10,
        )
        data = r.json()
        return {
            "used_gb": data.get("bandwidth_used", 0) / (1024 ** 3),
            "total_gb": data.get("bandwidth_limit", 0) / (1024 ** 3),
            "proxy_count": data.get("proxy_count", 0),
        }


async def test_proxy_connection(proxy: dict) -> dict:
    proxy_url = (
        f"socks5://{proxy['user']}:{proxy['pass']}"
        f"@{proxy['host']}:{proxy['port']}"
    )
    try:
        async with httpx.AsyncClient(
            proxies={"http://": proxy_url, "https://": proxy_url},
            timeout=12,
        ) as client:
            r = await client.get("http://ip-api.com/json")
            data = r.json()
            return {
                "working": True,
                "exit_ip": data.get("query"),
                "exit_geo": data.get("countryCode"),
                "isp": data.get("isp"),
                "geo_matches": data.get("countryCode", "").upper() == proxy.get("geo", "").upper(),
            }
    except Exception as e:
        return {"working": False, "error": str(e), "exit_ip": None, "exit_geo": None}


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
    }

    if not proxy["host"]:
        return {"status": "proxy_error", "proxy": {"working": False, "error": "No proxy configured"}, "smtp": None, "recommended_action": "add_proxy"}

    proxy_result = await test_proxy_connection(proxy)
    if not proxy_result["working"]:
        return {"status": "proxy_error", "proxy": proxy_result, "smtp": None, "recommended_action": "rotate_proxy"}

    smtp_result = await test_smtp_via_proxy(account["email"], account["password"], proxy)
    if not smtp_result["working"]:
        status = "smtp_blocked" if smtp_result.get("smtp") == "smtp_error" else "auth_failed"
        return {"status": status, "proxy": proxy_result, "smtp": smtp_result,
                "recommended_action": "check_account" if status == "auth_failed" else "wait_retry"}

    return {"status": "active", "proxy": proxy_result, "smtp": smtp_result, "recommended_action": "none"}


async def rotate_account_proxy(account_id: int, geo: str, db) -> dict:
    from app.db.models.accounts import SenderAccount
    from app.core.security import encrypt_secret

    new_proxy = await get_fresh_proxy(geo)
    if not new_proxy:
        return {"success": False, "error": f"No proxies available for geo: {geo}"}

    test = await test_proxy_connection(new_proxy)
    if not test["working"]:
        return {"success": False, "error": "New proxy also failed health check"}

    from sqlalchemy import select
    result = await db.execute(select(SenderAccount).where(SenderAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        return {"success": False, "error": "Account not found"}

    account.proxy_host = new_proxy["host"]
    account.proxy_port = new_proxy["port"]
    account.proxy_user = new_proxy["user"]
    account.proxy_pass = encrypt_secret(new_proxy["pass"])
    account.status = "active"
    await db.commit()

    return {"success": True, "new_proxy": {k: v for k, v in new_proxy.items() if k != "pass"}, "test": test}
