# SKILL: Send Flow — How Campaigns Are Sent

## Overview

The send flow is the core of the system. It extends `snd.py` with proxy-per-account support, affiliate offer integration, blacklist/suppression filtering, and Google Cloud Console script generation.

---

## Send Page — Step by Step

### Step 1: Select Sender Account Groups

- Choose which **groups** of Gmail/GSuite accounts to use
- System shows: total accounts in group, active count, blocked count
- Can select multiple groups → accounts are merged into a pool
- Each account will be assigned a portion of the recipient list

### Step 2: Select Recipient Lists

- Choose one or more recipient lists (uploaded TXT/CSV files)
- System shows: total count, already-sent count, remaining
- Lists are merged and deduplicated

### Step 3: Choose Offer

- Select affiliate network → select offer
- System auto-loads:
  - Tracking URL (with sub parameters filled based on network config)
  - Offer data fields (landing URL, discount, product name, etc.)
  - Suppression list (how many recipients will be filtered)

### Step 4: Compose

- **Header**: From name, From email (or auto from account), Subject, custom headers
- **Body**: HTML editor with tag support + preview
- **Negative content**: Content for `[negative]` tag (junk text for spam filters)
- **Links**: List of URLs for `[LinksPlaceholder]` rotation

### Step 5: Configuration

```
Batch Size:           1-100 recipients per batch
Sleep Between:        seconds to wait between batches  
Max Workers:          concurrent threads (ThreadPoolExecutor)
Max per Account:      max emails each account sends
Send Mode:            mx_direct (snd.py style) | smtp (Gmail SMTP)
```

### Step 6: Pre-Send Check

System shows:
- Total recipients: `N`
- After suppression filter: `N - X suppressed`
- After blacklist filter: `N - Y blacklisted`
- **Final send count**: clean recipients
- Accounts available: `Z accounts active`
- Estimated time: based on batch size + sleep

### Step 7: Test Email

- Enter a test email address
- System sends ONE email using first available account
- Shows full headers + body in preview
- Verify it arrives in inbox before launching

### Step 8: Launch → Generate Script

When user clicks **Send**, system:
1. Generates Python script (extension of `snd.py`) with all data embedded
2. Saves campaign to DB with status `running`
3. Shows link to open Google Cloud Console
4. User pastes/uploads script and runs it there

---

## Send Engine — Extended `snd.py`

```python
# services/mailer.py

import smtplib
import dns.resolver
import socks  # PySocks library for proxy support
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import email.utils
import uuid
import random
import string
import re
import datetime
import requests

# ============================================================
# PROXY-AWARE MX RESOLVER
# ============================================================

def get_mx_via_proxy(domain: str, proxy_config: dict) -> list:
    """
    Resolve MX records for domain, routing through SOCKS5 proxy.
    This ensures Google cannot trace the DNS lookup back to Cloud Shell.
    """
    # Patch socket to use SOCKS5 proxy
    socks.set_default_proxy(
        socks.SOCKS5,
        proxy_config["host"],
        int(proxy_config["port"]),
        username=proxy_config.get("user"),
        password=proxy_config.get("pass")
    )
    socket.socket = socks.socksocket
    
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1']  # Google/Cloudflare DNS
        records = resolver.resolve(domain, 'MX')
        mx_list = sorted(records, key=lambda r: r.preference)
        return [str(r.exchange) for r in mx_list]
    finally:
        # Restore normal socket after DNS lookup
        import importlib
        importlib.reload(socket)


# ============================================================
# PROXY-AWARE SMTP CONNECTION
# ============================================================

def get_smtp_via_proxy(mx_host: str, proxy_config: dict) -> smtplib.SMTP:
    """
    Open SMTP connection to MX server through SOCKS5 proxy.
    Connection path: Cloud Shell → Proxy → MX Server
    Google sees: Proxy IP (residential), not Cloud Shell IP
    """
    # Create a SOCKS5-wrapped socket
    proxy_socket = socks.socksocket()
    proxy_socket.set_proxy(
        socks.SOCKS5,
        proxy_config["host"],
        int(proxy_config["port"]),
        username=proxy_config.get("user"),
        password=proxy_config.get("pass")
    )
    proxy_socket.connect((mx_host.rstrip('.'), 25))
    
    smtp = smtplib.SMTP()
    smtp.sock = proxy_socket
    smtp.file = smtp.sock.makefile('rb')
    smtp._get_greeting()  # Read initial SMTP greeting
    smtp.ehlo()
    
    return smtp


# ============================================================
# MAIN SEND FUNCTION (per account)
# ============================================================

def send_account_batch(account: dict, recipients: list, campaign: dict):
    """
    Send a batch of emails from one account through its proxy.
    
    account = {
        "email": "sender@gmail.com",
        "password": "app_password",
        "proxy_host": "rp.webshare.io",
        "proxy_port": 5432,
        "proxy_user": "user123",
        "proxy_pass": "pass456",
        "geo": "US"
    }
    
    recipients = ["user1@gmail.com", "user2@yahoo.com", ...]
    
    campaign = {
        "header": "...",      # Raw header template
        "body_html": "...",   # HTML body template
        "links": [...],       # Links for [LinksPlaceholder]
        "negative": "...",    # Negative content
        "batch_size": 1,
        "sleep_between": 3,
        "max_workers": 5,
        "offer_data": {...}   # Offer fields for {{offer.X}} tags
    }
    """
    
    proxy_config = {
        "host": account["proxy_host"],
        "port": account["proxy_port"],
        "user": account["proxy_user"],
        "pass": account["proxy_pass"]
    }
    
    # Process templates with account + offer data
    tag_engine = TagEngine(
        campaign=campaign,
        account=account,
        links=campaign["links"],
        negative=campaign["negative"],
        offer_data=campaign.get("offer_data", {})
    )
    
    # Parse headers
    headers = tag_engine.process_header(campaign["header"])
    
    # Group recipients by domain for MX efficiency
    by_domain = group_by_domain(recipients)
    
    results = []
    
    for domain, domain_recipients in by_domain.items():
        try:
            # Resolve MX through proxy
            mx_records = get_mx_via_proxy(domain, proxy_config)
            
            # Batch recipients for this domain
            for i in range(0, len(domain_recipients), campaign["batch_size"]):
                batch = domain_recipients[i:i + campaign["batch_size"]]
                
                # Build message with fresh random tags per email
                for recipient_email in batch:
                    html_body = tag_engine.process_body(
                        campaign["body_html"],
                        recipient_email=recipient_email
                    )
                    
                    msg = build_message(headers, recipient_email, html_body, domain)
                    
                    # Try each MX server
                    sent = False
                    for mx in mx_records:
                        try:
                            smtp = get_smtp_via_proxy(mx, proxy_config)
                            smtp.sendmail(headers["from_email"], [recipient_email], msg.as_string())
                            smtp.quit()
                            
                            results.append({
                                "email": recipient_email,
                                "status": "sent",
                                "mx": mx,
                                "message_id": msg["Message-ID"]
                            })
                            sent = True
                            break
                            
                        except Exception as e:
                            continue
                    
                    if not sent:
                        results.append({
                            "email": recipient_email,
                            "status": "failed",
                            "error": "All MX servers failed"
                        })
                
                # Sleep between batches (with jitter for anti-detection)
                sleep_time = campaign["sleep_between"] * (0.7 + random.random() * 0.6)
                time.sleep(sleep_time)
                
        except Exception as e:
            for r in domain_recipients:
                results.append({"email": r, "status": "error", "error": str(e)})
    
    return results


# ============================================================
# MULTI-ACCOUNT PARALLEL SEND
# ============================================================

def run_campaign(accounts: list, recipients: list, campaign: dict):
    """
    Distribute recipients across accounts and send in parallel.
    Each account handles its own portion through its own proxy.
    """
    # Filter blacklist + suppression
    clean_recipients, filtered_count = filter_recipients(
        recipients, campaign.get("offer_id")
    )
    
    print(f"Total: {len(recipients)}, Filtered: {filtered_count}, Sending: {len(clean_recipients)}")
    
    # Split recipients evenly across accounts
    chunk_size = max(1, len(clean_recipients) // len(accounts))
    chunks = [
        clean_recipients[i:i + chunk_size]
        for i in range(0, len(clean_recipients), chunk_size)
    ]
    
    all_results = []
    
    with ThreadPoolExecutor(max_workers=campaign.get("max_workers", 5)) as executor:
        futures = {
            executor.submit(send_account_batch, accounts[i], chunks[i], campaign): accounts[i]["email"]
            for i in range(min(len(accounts), len(chunks)))
        }
        
        for future in as_completed(futures):
            account_email = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
                sent = sum(1 for r in results if r["status"] == "sent")
                print(f"Account {account_email}: {sent}/{len(results)} sent")
            except Exception as exc:
                print(f"Account {account_email} failed: {exc}")
    
    return all_results
```

---

## Script Generator for Google Cloud Console

```python
# services/script_gen.py

def generate_cloud_script(campaign: dict, accounts: list, recipients: list) -> str:
    """
    Generate a standalone Python script that can be run in Google Cloud Shell.
    The script embeds all campaign data and handles its own execution.
    Anti-detection: obfuscated variable names, random delays, no obvious patterns.
    """
    
    # Obfuscate variable names with random prefixes
    var_prefix = ''.join(random.choices(string.ascii_lowercase, k=3))
    
    # Encode sensitive data
    import base64
    accounts_b64 = base64.b64encode(json.dumps(accounts).encode()).decode()
    recipients_b64 = base64.b64encode(json.dumps(recipients).encode()).decode()
    
    script = f'''#!/usr/bin/env python3
# Generated script — do not modify
import base64, json, smtplib, dns.resolver, socks, socket
import time, random, string, re, uuid, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed

# Install deps if needed
import subprocess
subprocess.run(["pip", "install", "-q", "dnspython", "PySocks"], capture_output=True)

{var_prefix}_a = json.loads(base64.b64decode("{accounts_b64}"))
{var_prefix}_r = json.loads(base64.b64decode("{recipients_b64}"))
{var_prefix}_bs = {campaign["batch_size"]}
{var_prefix}_sl = {campaign["sleep_between"]}
{var_prefix}_mw = {campaign["max_workers"]}

# [... full snd.py logic embedded here with proxy support ...]

print("Campaign started:", datetime.datetime.now())
run_campaign({var_prefix}_a, {var_prefix}_r, campaign_config)
print("Done:", datetime.datetime.now())
'''
    
    return script
```

---

## Anti-Detection Measures

When running in Google Cloud Shell:

1. **All traffic routes through Webshare residential proxies** — Cloud Shell IP never touches Gmail MX servers
2. **Random delays with jitter** — `sleep_time = base_sleep * (0.7 + random() * 0.6)`
3. **Rotate Message-ID** — fresh UUID per email
4. **Rotate X-Mailer header** — random string each time
5. **Randomize send order** — `random.shuffle(recipients)` before sending
6. **Chunked sends** — never more than 50/hour per account
7. **Obfuscated script** — base64-encoded data, randomized variable names
8. **No repeated patterns** — random header values via `{n_X}`, `{an_X}` tags
9. **DNS resolution through proxy** — even MX lookups are proxied
10. **Connection timeout jitter** — random socket timeouts
