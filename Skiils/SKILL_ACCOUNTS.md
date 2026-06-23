# SKILL: Adding Sender Accounts (Gmail / GSuite) with Proxy

## Overview

This is the most critical part of the system. Each sender account (Gmail or GSuite/Google Workspace) must be paired with a dedicated proxy. The sending engine (`snd.py` logic) connects through the proxy before resolving MX records and sending.

---

## Account Format

When importing accounts in bulk, use this CSV format (one account per line):

```
email:password:proxy_host:proxy_port:proxy_user:proxy_pass:geo:type
```

### Example

```
john.doe@gmail.com:AppPass1234:rp.webshare.io:5432:user123:pass456:US:webshare_gb
business@gsuite.com:AppPass5678:rp.webshare.io:5432:user789:pass012:FR:webshare_gb
```

### Fields

| Field | Description | Example |
|-------|-------------|---------|
| `email` | Full Gmail or GSuite email | `sender@gmail.com` |
| `password` | Gmail App Password (NOT account password) | `abcd efgh ijkl mnop` |
| `proxy_host` | Webshare proxy hostname | `rp.webshare.io` |
| `proxy_port` | Proxy port | `5432` |
| `proxy_user` | Webshare proxy username | `abc123xyz` |
| `proxy_pass` | Webshare proxy password | `secretpass` |
| `geo` | Country code for proxy geo | `US`, `FR`, `GB`, `CA` |
| `type` | Proxy type | `webshare_gb`, `static`, `datacenter` |

---

## Gmail App Password (Required)

Gmail blocks direct password login. You MUST use an App Password:

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → 2-Step Verification → Enable it first
3. Security → App Passwords
4. Select "Mail" + "Other device" → name it "Mailer"
5. Copy the 16-char password → use it in the `password` field

**GSuite/Google Workspace**: Same process. Admin may need to allow less secure app access in Admin Console → Security → Basic Settings.

---

## How the Send Engine Uses the Account

From `snd.py` logic — extended with proxy support:

```python
# Each account sends through its own proxy
def send_via_account(account, recipients, campaign):
    """
    account.email       = from address
    account.password    = Gmail App Password
    account.proxy_host  = Webshare proxy host
    account.proxy_port  = Webshare proxy port
    account.proxy_user  = proxy auth user
    account.proxy_pass  = proxy auth pass
    """
    
    # Step 1: Route DNS (MX lookup) through proxy
    # snd.py uses dns.resolver — we patch it to use proxy SOCKS5
    resolver = get_proxy_resolver(account.proxy_host, account.proxy_port,
                                   account.proxy_user, account.proxy_pass)
    
    # Step 2: For each recipient domain, get MX records via proxy
    for domain, emails in group_by_domain(recipients).items():
        mx_records = resolver.resolve(domain, 'MX')
        
        # Step 3: Connect SMTP through proxy tunnel
        # Use socks5 tunnel: proxy → recipient MX server
        smtp_conn = get_smtp_via_proxy(mx_records[0], account)
        smtp_conn.sendmail(account.email, emails, build_message(campaign, emails))
    
    # Step 4: Log result to DB
    log_send_result(campaign.id, account.id, results)
```

**Key difference from basic snd.py**: Each account uses its OWN proxy, not a shared one. This prevents Google from associating sends from different accounts.

---

## Why Proxy Per Account?

- Google tracks sending IP per account
- If 10 accounts share 1 IP → Google flags them all together
- With proxy-per-account → each Gmail account has a unique IP identity
- Webshare GB (residential) = looks like a real person's home internet
- Google cannot distinguish it from normal Gmail usage

---

## Account Groups

Organize accounts into groups for targeted campaigns:

```
Group: "US Gmail Accounts"
  ├── sender1@gmail.com  (proxy: US)
  ├── sender2@gmail.com  (proxy: US)
  └── sender3@gmail.com  (proxy: US)

Group: "FR GSuite Accounts"
  ├── contact@company.fr  (proxy: FR)
  └── info@company.fr     (proxy: FR)
```

In the Send page, you select which groups to use for a campaign.

---

## Account Health Check

The system automatically checks each account's health:

1. **Proxy Test**: Connect to `http://ip-api.com/json` through the proxy → verify geo matches expected country
2. **SMTP Test**: Try authenticating with `smtp.gmail.com:587` through proxy → verify login works
3. **MX Test**: Resolve `gmail.com` MX records through proxy → verify DNS routing works

### Health Status Values

| Status | Meaning |
|--------|---------|
| `active` | Proxy working + SMTP auth OK |
| `proxy_error` | Proxy unreachable or blocked |
| `smtp_blocked` | Google blocked SMTP (security alert) |
| `auth_failed` | Wrong password or App Password expired |
| `testing` | Health check in progress |

### Auto-Recovery

- If `proxy_error` → rotate to new Webshare proxy automatically (via Webshare API)
- If `smtp_blocked` → mark account, skip in next send, notify admin
- Health checks run every 30 minutes via Celery beat scheduler

---

## Webshare GB Proxy Rotation

```python
# services/proxy.py
import requests

WEBSHARE_API_KEY = "your_webshare_api_key"
WEBSHARE_BASE_URL = "https://proxy.webshare.io/api/v2"

def get_fresh_proxy(geo: str = "US") -> dict:
    """Get a fresh residential GB proxy from Webshare for given geo"""
    response = requests.get(
        f"{WEBSHARE_BASE_URL}/proxy/list/",
        headers={"Authorization": f"Token {WEBSHARE_API_KEY}"},
        params={
            "mode": "direct",
            "country_code__in": geo,
            "valid": True,
            "page": 1,
            "page_size": 1
        }
    )
    proxies = response.json()["results"]
    if proxies:
        p = proxies[0]
        return {
            "host": p["proxy_address"],
            "port": p["ports"]["socks5"],
            "username": p["username"],
            "password": p["password"],
            "geo": p["country_code"]
        }
    return None

def rotate_account_proxy(account_id: int, geo: str):
    """Assign a new proxy to an account when current one fails"""
    new_proxy = get_fresh_proxy(geo)
    if new_proxy:
        db.update(SenderAccount, account_id, {
            "proxy_host": new_proxy["host"],
            "proxy_port": new_proxy["port"],
            "proxy_user": new_proxy["username"],
            "proxy_pass": new_proxy["password"],
            "status": "active"
        })
```

---

## Adding Accounts in the UI

### Single Account
1. Go to **Accounts** page → **Add Account**
2. Fill: Email, App Password, Proxy details, Geo, Group
3. Click **Test Connection** → system runs health check
4. If green → Save

### Bulk Import (CSV)
1. Go to **Accounts** → **Bulk Import**
2. Paste or upload file with format: `email:password:proxy_host:proxy_port:proxy_user:proxy_pass:geo:type`
3. System parses, deduplicates, and runs health check on each
4. Shows results: how many active, how many failed

---

## Important Notes

- **Never use your main Gmail password** — always App Password
- **One proxy per account** — do not share proxies between accounts
- **Rate limit**: max 500 emails/day per Gmail free account, more for GSuite
- **App Passwords expire** when you change your Google password → update in system
- **2FA required** on all Gmail accounts to enable App Passwords
