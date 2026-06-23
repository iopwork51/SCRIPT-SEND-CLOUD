# SKILL: Proxy Setup with Webshare GB

## Overview

Every sender account in the system must have a dedicated residential proxy. The system uses Webshare GB (residential gigabyte-based proxies) which are billed by bandwidth, not by number of IPs. This makes them ideal for email sending where each connection is small but you need many unique IPs.

---

## Why Residential Proxies for Email Sending

- **Gmail tracks sending IP per account** — if many accounts share one IP, Google links them
- **Datacenter IPs are flagged** — Gmail instantly recognizes AWS/GCP/Cloudflare IP ranges
- **Residential IPs = trusted** — they look like real home internet users
- **Webshare GB specifically** — you pay per GB of traffic used, not per proxy. Email sends use very little bandwidth (< 1MB per 1000 emails), making this extremely cost-effective

---

## Webshare API Integration

### Base URL
```
https://proxy.webshare.io/api/v2
```

### Authentication
```
Authorization: Token YOUR_WEBSHARE_API_KEY
```

Get your API key from: https://proxy.webshare.io/userapi/keys

---

## Full Proxy Service Implementation

```python
# services/proxy.py

import httpx
import socks
import socket
import smtplib
import asyncio
from typing import Optional
from app.core.config import settings

WEBSHARE_API_KEY = settings.WEBSHARE_API_KEY
WEBSHARE_BASE = "https://proxy.webshare.io/api/v2"


# ============================================================
# WEBSHARE API CALLS
# ============================================================

async def get_proxy_list(geo: str = None, page_size: int = 100) -> list:
    """
    Fetch list of available residential proxies from Webshare.
    Filter by country code if geo is provided.
    """
    params = {
        "mode": "direct",
        "valid": True,
        "page": 1,
        "page_size": page_size
    }
    if geo:
        params["country_code__in"] = geo.upper()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/proxy/list/",
            headers={"Authorization": f"Token {WEBSHARE_API_KEY}"},
            params=params,
            timeout=15
        )
        r.raise_for_status()
        return r.json().get("results", [])


async def get_fresh_proxy(geo: str = "US") -> Optional[dict]:
    """
    Get one fresh proxy for a specific country.
    Returns dict with host, port, user, pass, geo.
    """
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
        "type": "socks5"
    }


async def get_proxy_usage() -> dict:
    """
    Get current bandwidth usage from Webshare.
    Returns used GB and total GB in plan.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/profile/",
            headers={"Authorization": f"Token {WEBSHARE_API_KEY}"},
            timeout=10
        )
        data = r.json()
        return {
            "used_gb": data.get("bandwidth_used", 0) / (1024**3),
            "total_gb": data.get("bandwidth_limit", 0) / (1024**3),
            "proxy_count": data.get("proxy_count", 0)
        }


# ============================================================
# PROXY HEALTH CHECK
# ============================================================

async def test_proxy_connection(proxy: dict) -> dict:
    """
    Test if proxy is reachable and verify its geo.
    Uses ip-api.com to confirm the exit IP country.
    """
    proxy_url = (
        f"socks5://{proxy['user']}:{proxy['pass']}"
        f"@{proxy['host']}:{proxy['port']}"
    )
    try:
        async with httpx.AsyncClient(
            proxies={"http://": proxy_url, "https://": proxy_url},
            timeout=12
        ) as client:
            r = await client.get("http://ip-api.com/json")
            data = r.json()
            return {
                "working": True,
                "exit_ip": data.get("query"),
                "exit_geo": data.get("countryCode"),
                "isp": data.get("isp"),
                "geo_matches": data.get("countryCode", "").upper() == proxy.get("geo", "").upper()
            }
    except Exception as e:
        return {
            "working": False,
            "error": str(e),
            "exit_ip": None,
            "exit_geo": None
        }


async def test_smtp_via_proxy(account_email: str, account_password: str, proxy: dict) -> dict:
    """
    Test Gmail SMTP authentication through the account's proxy.
    This verifies the full chain: proxy → Gmail SMTP → auth.
    
    Uses SOCKS5 to tunnel through proxy to smtp.gmail.com:587
    """
    try:
        # Create SOCKS5 proxy socket
        proxy_sock = socks.socksocket()
        proxy_sock.set_proxy(
            socks.SOCKS5,
            proxy["host"],
            int(proxy["port"]),
            username=proxy.get("user"),
            password=proxy.get("pass")
        )
        proxy_sock.settimeout(15)
        proxy_sock.connect(("smtp.gmail.com", 587))

        # Wrap in SMTP
        smtp = smtplib.SMTP()
        smtp.sock = proxy_sock
        smtp.file = smtp.sock.makefile("rb")
        smtp._get_reply()  # Read SMTP greeting
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(account_email, account_password)
        smtp.quit()

        return {"working": True, "smtp": "authenticated", "error": None}

    except smtplib.SMTPAuthenticationError:
        return {"working": False, "smtp": "auth_failed",
                "error": "Wrong password or App Password expired"}
    except smtplib.SMTPException as e:
        return {"working": False, "smtp": "smtp_error", "error": str(e)}
    except socks.ProxyError as e:
        return {"working": False, "smtp": "proxy_error", "error": f"Proxy failed: {e}"}
    except Exception as e:
        return {"working": False, "smtp": "connection_error", "error": str(e)}


async def full_account_health_check(account: dict) -> dict:
    """
    Run complete health check for a sender account:
    1. Test proxy reachability + geo
    2. Test Gmail SMTP auth through proxy
    
    Returns combined result and recommended status.
    """
    proxy = {
        "host": account["proxy_host"],
        "port": account["proxy_port"],
        "user": account["proxy_user"],
        "pass": account["proxy_pass"],
        "geo": account["proxy_geo"]
    }

    # Step 1: Proxy test
    proxy_result = await test_proxy_connection(proxy)

    if not proxy_result["working"]:
        return {
            "status": "proxy_error",
            "proxy": proxy_result,
            "smtp": None,
            "recommended_action": "rotate_proxy"
        }

    # Step 2: SMTP auth test
    smtp_result = await test_smtp_via_proxy(
        account["email"],
        account["password"],
        proxy
    )

    if not smtp_result["working"]:
        status = "smtp_blocked" if "smtp_error" in smtp_result.get("smtp", "") else "auth_failed"
        return {
            "status": status,
            "proxy": proxy_result,
            "smtp": smtp_result,
            "recommended_action": "check_account" if status == "auth_failed" else "wait_retry"
        }

    return {
        "status": "active",
        "proxy": proxy_result,
        "smtp": smtp_result,
        "recommended_action": "none"
    }


# ============================================================
# PROXY ROTATION
# ============================================================

async def rotate_account_proxy(account_id: int, geo: str, db) -> dict:
    """
    Get a new proxy from Webshare and assign it to the account.
    Called automatically when proxy_error is detected.
    """
    from app.db.models.accounts import SenderAccount

    new_proxy = await get_fresh_proxy(geo)
    if not new_proxy:
        return {"success": False, "error": f"No proxies available for geo: {geo}"}

    # Verify new proxy works before assigning
    test = await test_proxy_connection(new_proxy)
    if not test["working"]:
        return {"success": False, "error": "New proxy also failed health check"}

    # Update account in DB
    await db.execute(
        SenderAccount.__table__.update()
        .where(SenderAccount.id == account_id)
        .values(
            proxy_host=new_proxy["host"],
            proxy_port=new_proxy["port"],
            proxy_user=new_proxy["user"],
            proxy_pass=new_proxy["pass"],
            status="active"
        )
    )
    await db.commit()

    return {"success": True, "new_proxy": new_proxy, "test": test}
```

---

## SOCKS5 Proxy in Send Engine (MX Direct)

When sending email via MX (like snd.py), ALL traffic routes through the proxy:

```python
# How proxy is used in mailer.py

import socks
import socket as stdlib_socket

def create_proxy_smtp_to_mx(mx_host: str, proxy: dict) -> smtplib.SMTP:
    """
    Open SMTP connection to recipient's MX server through SOCKS5 proxy.
    
    Traffic path:
    Cloud Shell → [SOCKS5 Proxy] → MX Server
    
    MX server sees: Proxy IP (residential, looks like home user)
    Google Cloud Shell IP is never exposed.
    """
    # Create SOCKS5-wrapped socket
    sock = socks.socksocket(stdlib_socket.AF_INET, stdlib_socket.SOCK_STREAM)
    sock.set_proxy(
        socks.SOCKS5,
        proxy["host"],
        int(proxy["port"]),
        username=proxy.get("user"),
        password=proxy.get("pass")
    )
    sock.settimeout(20)

    # Connect to MX server port 25 through proxy
    mx_clean = mx_host.rstrip(".")
    sock.connect((mx_clean, 25))

    # Wrap socket in SMTP object
    smtp = smtplib.SMTP()
    smtp.sock = sock
    smtp.file = smtp.sock.makefile("rb")
    smtp._get_reply()  # Read SMTP banner
    smtp.ehlo()

    return smtp


def get_mx_via_proxy(domain: str, proxy: dict) -> list:
    """
    Resolve MX records for domain, routing DNS through SOCKS5 proxy.
    Prevents MX lookup from revealing Cloud Shell IP.
    """
    # Temporarily patch socket to route through SOCKS5
    original_socket = stdlib_socket.socket
    socks.set_default_proxy(
        socks.SOCKS5,
        proxy["host"],
        int(proxy["port"]),
        username=proxy.get("user"),
        password=proxy.get("pass")
    )
    stdlib_socket.socket = socks.socksocket

    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        records = resolver.resolve(domain, "MX")
        mx_list = sorted(records, key=lambda r: r.preference)
        return [str(r.exchange) for r in mx_list]
    finally:
        # Always restore the original socket
        stdlib_socket.socket = original_socket
        socks.set_default_proxy()
```

---

## Proxy Formats Supported

| Format | Example |
|--------|---------|
| Webshare GB SOCKS5 | `rp.webshare.io:5432:user:pass` |
| Webshare GB HTTP | `rp.webshare.io:8080:user:pass` |
| Static residential | `proxy.host.com:1080:user:pass` |
| Datacenter (not recommended) | `dc.host.com:3128:user:pass` |

---

## CSV Import Format for Accounts

```
email:app_password:proxy_host:proxy_port:proxy_user:proxy_pass:geo:proxy_type
```

Example:
```
sender1@gmail.com:abcd efgh ijkl mnop:rp.webshare.io:5432:ws_user1:ws_pass1:US:webshare_gb
sender2@gmail.com:qrst uvwx yzab cdef:rp.webshare.io:5432:ws_user2:ws_pass2:FR:webshare_gb
business@company.com:mnop qrst uvwx yzab:rp.webshare.io:5432:ws_user3:ws_pass3:GB:webshare_gb
```

Parser:
```python
def parse_account_csv_line(line: str) -> dict:
    parts = line.strip().split(":")
    if len(parts) < 8:
        raise ValueError(f"Invalid format: {line}")
    return {
        "email": parts[0],
        "password": parts[1],
        "proxy_host": parts[2],
        "proxy_port": int(parts[3]),
        "proxy_user": parts[4],
        "proxy_pass": parts[5],
        "proxy_geo": parts[6].upper(),
        "proxy_type": parts[7]
    }
```

---

## Scheduled Health Checks (Celery Beat)

```python
# tasks/health_tasks.py

from celery import shared_task
from app.services.proxy import full_account_health_check, rotate_account_proxy

@shared_task
async def check_all_accounts():
    """Run every 30 minutes via Celery beat"""
    accounts = await db.query(SenderAccount).filter(SenderAccount.is_deleted == False).all()
    
    for account in accounts:
        result = await full_account_health_check(account.__dict__)
        
        # Update status in DB
        await db.execute(
            SenderAccount.__table__.update()
            .where(SenderAccount.id == account.id)
            .values(
                status=result["status"],
                last_health_check=datetime.utcnow()
            )
        )
        
        # Auto-rotate proxy if needed
        if result["status"] == "proxy_error" and result["recommended_action"] == "rotate_proxy":
            await rotate_account_proxy(account.id, account.proxy_geo, db)
        
        # Notify admin if account is blocked
        if result["status"] in ["smtp_blocked", "auth_failed"]:
            await notify_admin(account.email, result["status"])
    
    await db.commit()

# Celery beat schedule (in celeryconfig.py):
# "check-accounts": {
#     "task": "tasks.health_tasks.check_all_accounts",
#     "schedule": 1800.0  # every 30 minutes
# }
```
