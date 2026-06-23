"""
Send engine — extends snd.py with proxy-per-account support, anti-detection,
and filter pipeline. Used for test sends; bulk sends run via generated scripts.
"""

import smtplib
import dns.resolver
import socks
import socket as stdlib_socket
import importlib
import uuid
import random
import string
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import time

from app.services.tags import replace_tags, process_header


def get_mx_via_proxy(domain: str, proxy: dict) -> list[str]:
    """Resolve MX records routing DNS through SOCKS5 proxy."""
    socks.set_default_proxy(
        socks.SOCKS5,
        proxy["host"],
        int(proxy["port"]),
        username=proxy.get("user"),
        password=proxy.get("pass"),
    )
    stdlib_socket.socket = socks.socksocket

    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "1.1.1.1"]
        records = resolver.resolve(domain, "MX")
        mx_list = sorted(records, key=lambda r: r.preference)
        return [str(r.exchange) for r in mx_list]
    finally:
        importlib.reload(stdlib_socket)


def get_smtp_via_proxy(mx_host: str, proxy: dict) -> smtplib.SMTP:
    """Open SMTP connection to MX server through SOCKS5 proxy."""
    proxy_socket = socks.socksocket()
    proxy_socket.set_proxy(
        socks.SOCKS5,
        proxy["host"],
        int(proxy["port"]),
        username=proxy.get("user"),
        password=proxy.get("pass"),
    )
    proxy_socket.settimeout(20)
    mx_clean = mx_host.rstrip(".")
    proxy_socket.connect((mx_clean, 25))

    smtp = smtplib.SMTP()
    smtp.sock = proxy_socket
    smtp.file = smtp.sock.makefile("rb")
    smtp._get_reply()
    smtp.ehlo()
    return smtp


def send_one_email(
    account: dict,
    to_email: str,
    from_email: str,
    from_name: str,
    subject: str,
    html_body: str,
    extra_headers: dict | None = None,
    send_mode: str = "mx_direct",
) -> dict:
    """Send a single email through an account's proxy."""
    proxy = {
        "host": account["proxy_host"],
        "port": account["proxy_port"],
        "user": account["proxy_user"],
        "pass": account.get("proxy_pass"),
    }

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Message-ID"] = f"<{uuid.uuid4()}@{to_email.split('@')[1]}>"
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["X-Mailer"] = "".join(random.choices(string.ascii_letters + string.digits, k=12))

    if extra_headers:
        for name, value in extra_headers.items():
            if name.lower() not in ["from", "subject", "to", "message-id", "date"]:
                msg[name] = value

    msg.attach(MIMEText(html_body, "html"))

    if send_mode == "smtp":
        return _send_via_smtp(account, from_email, [to_email], msg)
    else:
        return _send_via_mx(proxy, from_email, to_email, msg)


def _send_via_mx(proxy: dict, from_email: str, to_email: str, msg) -> dict:
    domain = to_email.split("@")[1]
    try:
        mx_list = get_mx_via_proxy(domain, proxy)
    except Exception as e:
        return {"success": False, "error": f"MX lookup failed: {e}", "mx": None}

    for mx in mx_list:
        try:
            smtp = get_smtp_via_proxy(mx, proxy)
            smtp.sendmail(from_email, [to_email], msg.as_string())
            smtp.quit()
            return {"success": True, "mx": mx, "error": None}
        except Exception as e:
            continue

    return {"success": False, "error": "All MX servers failed", "mx": None}


def _send_via_smtp(account: dict, from_email: str, to_emails: list, msg) -> dict:
    proxy = {
        "host": account["proxy_host"],
        "port": account["proxy_port"],
        "user": account["proxy_user"],
        "pass": account.get("proxy_pass"),
    }
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
        smtp.login(account["email"], account["password"])
        smtp.sendmail(from_email, to_emails, msg.as_string())
        smtp.quit()
        return {"success": True, "mx": "smtp.gmail.com", "error": None}
    except Exception as e:
        return {"success": False, "error": str(e), "mx": None}


async def send_test_via_account(account: dict, to_email: str, campaign) -> dict:
    """Send a single test email for campaign preview."""
    fixed = {}
    link_index = [0]
    links = campaign.links or []
    negative = campaign.negative_content or ""

    context = {
        "email": to_email,
        "first_name": to_email.split("@")[0],
        "campaign_id": campaign.id,
        "account_email": account["email"],
    }

    headers = process_header(
        campaign.header_template or "From: Test <test@test.com>\nSubject: Test",
        context, fixed, links, link_index, negative,
    )
    body = replace_tags(campaign.body_html or "<p>Test</p>", context, fixed, links, link_index, negative)

    result = send_one_email(
        account=account,
        to_email=to_email,
        from_email=headers.get("from_email", account["email"]),
        from_name=headers.get("from_name", "Test"),
        subject=headers.get("subject", "Test"),
        html_body=body,
        send_mode=campaign.send_mode,
    )
    return result
