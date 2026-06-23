# MailerPro — Master Build Prompt for Claude Opus Pro

## CONTEXT

You are building a professional bulk email sending platform called **MailerPro**. The system is used to send large volumes of email campaigns through Gmail and GSuite accounts, each paired with a dedicated residential proxy (Webshare GB). Campaigns are executed via Google Cloud Shell using a generated Python script based on `snd.py` (provided below).

---

## ORIGINAL SEND ENGINE (`snd.py`)

```python
import smtplib
import dns.resolver
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

BATCH_SIZE = 1
HTML_FILE_PATH = '1-body.html'
EMAIL_LIST_FILE_PATH = '2-data.txt'
HEADER_FILE_PATH = '0-header.txt'
NEGATIVE_FILE_PATH = '4-negative.txt'
MAX_WORKERS = 5
SLEEP_BETWEEN_BATCHES = 3

fixed_random_values = {}
link_index = 0

def generate_random_string(length, char_type, random_length=None):
    if random_length is None:
        if char_type == 'a': return ''.join(random.choices(string.ascii_letters, k=length))
        if char_type == 'al': return ''.join(random.choices(string.ascii_lowercase, k=length))
        if char_type == 'au': return ''.join(random.choices(string.ascii_uppercase, k=length))
        if char_type == 'an': return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        if char_type == 'anl': return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
        if char_type == 'anu': return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if char_type == 'n': return ''.join(random.choices(string.digits, k=length))
    else:
        return ''.join(random.choices(string.ascii_letters, k=random_length))

def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()
    except FileNotFoundError:
        print(f"{file_path} not found."); return ''

def replace_tags(text):
    global link_index
    negative_content = read_file(NEGATIVE_FILE_PATH)
    pattern = r'\{(a|al|au|an|anl|anu|n)_(\d+)\}'
    match = re.search(pattern, text)
    while match:
        char_type, length_str = match.groups()
        replacement = generate_random_string(int(length_str), char_type)
        text = text[:match.start()] + replacement + text[match.end():]
        match = re.search(pattern, text)
    text = re.sub(r'\[mail_date\]', datetime.date.today().strftime('%Y-%m-%d'), text)
    pattern = r'\[(a|al|au|an|anl|anu|n)_(\d+)\]'
    match = re.search(pattern, text)
    while match:
        char_type, length_str = match.groups()
        tag = match.group()
        if tag not in fixed_random_values:
            fixed_random_values[tag] = generate_random_string(int(length_str), char_type)
        text = text[:match.start()] + fixed_random_values[tag] + text[match.end():]
        match = re.search(pattern, text)
    try:
        with open('3-links.txt', 'r') as f: links = f.read().splitlines()
        text = text.replace('[LinksPlaceholder]', links[link_index])
        link_index = (link_index + 1) % len(links)
    except FileNotFoundError: pass
    text = text.replace('[negative]', negative_content)
    return text

def process_header_file(file_path):
    headers = {}
    with open(file_path, 'r') as f: content = f.read()
    processed_content = replace_tags(content)
    for line in processed_content.splitlines():
        if line.startswith('From:'):
            headers['from_email'] = re.search(r'<([^>]+)>', line).group(1)
            headers['from_name'] = re.search(r'From:\s*([^<]+)', line).group(1).strip()
        elif line.startswith('Subject:'):
            headers['subject'] = re.search(r'Subject:\s*(.*)', line).group(1).strip()
        else:
            if ':' in line:
                name, value = line.split(':', 1)
                headers[name.strip()] = value.strip()
    return headers

def get_mx_records(domain):
    records = dns.resolver.resolve(domain, 'MX')
    mx_records = sorted(records, key=lambda r: r.preference)
    return [str(r.exchange) for r in mx_records]

def send_email_via_mx(to_emails, headers, html_body):
    if not to_emails: return
    from_email = headers.get('from_email', '')
    domain = to_emails[0].split('@')[1]
    mx_records = get_mx_records(domain)
    msg = MIMEMultipart()
    msg['Subject'] = replace_tags(headers.get('subject', ''))
    msg['From'] = f"{replace_tags(headers.get('from_name',''))} <{replace_tags(from_email)}>"
    msg['To'] = replace_tags(from_email)
    msg['Bcc'] = '; '.join(replace_tags(e) for e in to_emails)
    for name, value in headers.items():
        if name.lower() not in ['from','subject','from_email','from_name']:
            msg[name] = replace_tags(value)
    msg['Message-ID'] = f"<{uuid.uuid4()}@{domain}>"
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(replace_tags(html_body), 'html'))
    for mx in mx_records:
        try:
            with smtplib.SMTP(mx) as server:
                server.sendmail(from_email, to_emails, msg.as_string())
                print(f"Sent {len(to_emails)} via {mx}")
                break
        except Exception as e:
            print(f"Failed via {mx}: {e}")

headers = process_header_file(HEADER_FILE_PATH)
html_body = open(HTML_FILE_PATH, 'r', encoding='utf-8').read()
email_list = [l.strip() for l in open(EMAIL_LIST_FILE_PATH) if l.strip()]
batches = list((email_list[i:i+BATCH_SIZE] for i in range(0, len(email_list), BATCH_SIZE)))

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(send_email_via_mx, b, headers, html_body) for b in batches]
    time.sleep(SLEEP_BETWEEN_BATCHES)
    for f in as_completed(futures):
        try: f.result()
        except Exception as exc: print(f"Exception: {exc}")

print("All emails sent.")
```

---

## TECH STACK

- **Backend**: Python 3.11 + FastAPI (fully async)
- **Database**: PostgreSQL 15 + SQLAlchemy async ORM + Alembic migrations
- **Queue**: Redis 7 + Celery 5 with beat scheduler
- **Frontend**: React 18 + TailwindCSS + shadcn/ui components
- **Proxy**: Webshare API — residential GB proxy rotation
- **Auth**: JWT (access 1h + refresh 7d) + bcrypt password hashing
- **Deployment**: Google Cloud Run + Cloud SQL

---

## DATABASE SCHEMA

### Users & Auth
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name VARCHAR,
    role VARCHAR NOT NULL DEFAULT 'mailer',  -- 'admin' | 'mailer'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    refresh_token VARCHAR UNIQUE NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Sender Accounts (Gmail / GSuite)
```sql
CREATE TABLE sender_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sender_accounts (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL,           -- Gmail App Password (encrypted at rest)
    account_type VARCHAR DEFAULT 'gmail', -- 'gmail' | 'gsuite' | 'smtp'
    
    -- Proxy config (Webshare GB)
    proxy_host VARCHAR,
    proxy_port INTEGER,
    proxy_user VARCHAR,
    proxy_pass VARCHAR,
    proxy_geo VARCHAR(5),               -- 'US', 'FR', 'GB', 'CA', etc.
    proxy_type VARCHAR DEFAULT 'webshare_gb',
    
    -- Group assignment
    group_id INTEGER REFERENCES sender_groups(id),
    user_id INTEGER REFERENCES users(id),
    
    -- Health tracking
    status VARCHAR DEFAULT 'testing',   -- 'active' | 'proxy_error' | 'smtp_blocked' | 'auth_failed' | 'testing'
    last_health_check TIMESTAMP,
    last_send TIMESTAMP,
    total_sent INTEGER DEFAULT 0,
    daily_sent INTEGER DEFAULT 0,
    daily_reset_at TIMESTAMP,
    
    -- Limits
    max_per_day INTEGER DEFAULT 500,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Recipient Lists
```sql
CREATE TABLE recipient_lists (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    total_count INTEGER DEFAULT 0,
    active_count INTEGER DEFAULT 0,
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE recipients (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL,
    name VARCHAR,
    list_id INTEGER REFERENCES recipient_lists(id) ON DELETE CASCADE,
    status VARCHAR DEFAULT 'active',    -- 'active' | 'unsubscribed' | 'bounced' | 'suppressed'
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_recipients_list_id ON recipients(list_id);
CREATE INDEX idx_recipients_email ON recipients(email);
```

### Affiliate Networks & Offers
```sql
CREATE TABLE affiliate_networks (
    id SERIAL PRIMARY KEY,
    affiliate_id VARCHAR,               -- External ID in their system
    name VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'activated', -- 'activated' | 'deactivated'
    website_url VARCHAR,
    
    -- Auth credentials
    username VARCHAR,
    password VARCHAR,
    
    -- API config
    api_platform VARCHAR DEFAULT 'none', -- 'none' | 'everflow' | 'cake' | 'hitpath' | 'custom'
    network_id VARCHAR,                  -- Required for Cake
    company_name VARCHAR,                -- Required for HitPath
    api_key VARCHAR,                     -- Everflow, custom
    api_username VARCHAR,                -- Geniads, custom
    api_password VARCHAR,                -- Geniads, custom
    
    -- Sub parameter tracking config (JSON)
    -- e.g. {"sub1": ["mailer_id", "list_id"], "sub2": ["process_id"], "sub3": ["email_id"]}
    sub_config JSONB DEFAULT '{}',
    
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE offers (
    id SERIAL PRIMARY KEY,
    network_id INTEGER REFERENCES affiliate_networks(id),
    external_id VARCHAR,                -- ID in affiliate network
    name VARCHAR NOT NULL,
    description TEXT,
    
    -- URLs
    tracking_url VARCHAR,               -- Click tracking URL
    preview_url VARCHAR,                -- Landing page
    
    -- Financials
    payout DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Email creative (from API)
    suggested_subject VARCHAR,
    suggested_from_name VARCHAR,
    html_creative TEXT,
    
    -- Config
    is_active BOOLEAN DEFAULT TRUE,
    max_sends_per_day INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE offer_data_fields (
    id SERIAL PRIMARY KEY,
    offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    field_key VARCHAR NOT NULL,         -- e.g. 'landing_url', 'discount_code'
    field_value TEXT,
    data_type VARCHAR DEFAULT 'text',   -- 'text' | 'url' | 'number' | 'html'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Suppression & Blacklists
```sql
CREATE TABLE blacklist (
    id SERIAL PRIMARY KEY,
    email VARCHAR,
    domain VARCHAR,
    reason VARCHAR,
    source VARCHAR DEFAULT 'manual',    -- 'manual' | 'bounce' | 'import' | 'offer'
    offer_id INTEGER REFERENCES offers(id),
    added_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_blacklist_email ON blacklist(email);
CREATE INDEX idx_blacklist_domain ON blacklist(domain);

CREATE TABLE suppression_list (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL,
    offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    imported_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_suppression_email_offer ON suppression_list(email, offer_id);
```

### Campaigns & Send Logs
```sql
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    user_id INTEGER REFERENCES users(id),
    
    -- Content
    header_template TEXT,               -- Raw header file content with tags
    body_html TEXT,                     -- HTML body with tags
    negative_content TEXT,
    links TEXT[],                       -- Array of links for [LinksPlaceholder]
    
    -- Assignment
    offer_id INTEGER REFERENCES offers(id),
    
    -- Config
    batch_size INTEGER DEFAULT 1,
    sleep_between INTEGER DEFAULT 3,
    max_workers INTEGER DEFAULT 5,
    send_mode VARCHAR DEFAULT 'mx_direct', -- 'mx_direct' | 'smtp'
    
    -- Status
    status VARCHAR DEFAULT 'draft',     -- 'draft' | 'running' | 'paused' | 'completed' | 'failed'
    total_recipients INTEGER DEFAULT 0,
    total_sent INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_filtered INTEGER DEFAULT 0,
    
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE campaign_account_groups (
    campaign_id INTEGER REFERENCES campaigns(id),
    group_id INTEGER REFERENCES sender_groups(id),
    PRIMARY KEY (campaign_id, group_id)
);

CREATE TABLE campaign_recipient_lists (
    campaign_id INTEGER REFERENCES campaigns(id),
    list_id INTEGER REFERENCES recipient_lists(id),
    PRIMARY KEY (campaign_id, list_id)
);

CREATE TABLE send_logs (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    account_id INTEGER REFERENCES sender_accounts(id),
    recipient_email VARCHAR NOT NULL,
    status VARCHAR NOT NULL,            -- 'sent' | 'failed' | 'bounced' | 'filtered'
    mx_server VARCHAR,
    proxy_host VARCHAR,
    message_id VARCHAR,
    error_message TEXT,
    sent_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_send_logs_campaign ON send_logs(campaign_id);
CREATE INDEX idx_send_logs_status ON send_logs(status);
```

---

## API ROUTES (FastAPI)

### Auth
```
POST /api/auth/login          → {access_token, refresh_token}
POST /api/auth/refresh        → {access_token}
POST /api/auth/logout
GET  /api/auth/me             → current user
```

### Users (admin only)
```
GET    /api/users             → list all users
POST   /api/users             → create user {email, password, role, full_name}
PUT    /api/users/{id}        → update user
DELETE /api/users/{id}        → deactivate user
```

### Sender Accounts
```
GET    /api/accounts          → list accounts (with group filter)
POST   /api/accounts          → add single account
POST   /api/accounts/bulk     → bulk import CSV (email:pass:proxy_host:port:user:pass:geo:type)
PUT    /api/accounts/{id}     → update account
DELETE /api/accounts/{id}     → remove account
POST   /api/accounts/{id}/test → run health check (proxy + SMTP test)
POST   /api/accounts/test-all  → run health check on all accounts
POST   /api/accounts/{id}/rotate-proxy → get new Webshare proxy
```

### Groups
```
GET    /api/groups            → list groups with account counts
POST   /api/groups            → create group
PUT    /api/groups/{id}       → update
DELETE /api/groups/{id}       → delete
GET    /api/groups/{id}/accounts → accounts in group
```

### Recipient Lists
```
GET    /api/recipients/lists  → list all lists
POST   /api/recipients/lists  → create list (name, description)
POST   /api/recipients/lists/{id}/upload → upload TXT/CSV file
DELETE /api/recipients/lists/{id} → delete list and all recipients
GET    /api/recipients/lists/{id}/count → stats
```

### Affiliate Networks
```
GET    /api/affiliates        → list networks
POST   /api/affiliates        → create network (all fields from screenshot)
PUT    /api/affiliates/{id}   → update
DELETE /api/affiliates/{id}   → delete
POST   /api/affiliates/{id}/test → test API connection
```

### Offers
```
GET    /api/offers            → list offers (filter by network)
POST   /api/offers/import     → import from affiliate API {network_id, offer_ids[], get_all, max_creatives}
POST   /api/offers            → create manually
PUT    /api/offers/{id}       → update
DELETE /api/offers/{id}       → delete
GET    /api/offers/{id}/data  → get data fields
POST   /api/offers/{id}/data  → add data field
PUT    /api/offers/{id}/data/{field_id} → update field
DELETE /api/offers/{id}/data/{field_id} → delete field
POST   /api/offers/{id}/sync-suppression → re-import suppression from API
```

### Blacklist & Suppression
```
GET    /api/blacklist         → list blacklisted emails/domains
POST   /api/blacklist         → add email or domain
POST   /api/blacklist/import  → bulk import from file
DELETE /api/blacklist/{id}    → remove
GET    /api/suppression       → list (filter by offer)
POST   /api/suppression/import → import for specific offer
```

### Campaigns & Send
```
GET    /api/campaigns         → list campaigns
POST   /api/campaigns         → create campaign
GET    /api/campaigns/{id}    → get campaign details
PUT    /api/campaigns/{id}    → update campaign
POST   /api/campaigns/{id}/preview → send test email
POST   /api/campaigns/{id}/generate-script → generate Cloud Console Python script
POST   /api/campaigns/{id}/start → launch campaign
POST   /api/campaigns/{id}/pause → pause running campaign
GET    /api/campaigns/{id}/stats  → live stats (sent, failed, filtered)
GET    /api/campaigns/{id}/logs   → send logs (paginated)
```

---

## AFFILIATE API INTEGRATIONS

### Everflow (https://docs.everflow.io/)
```python
class EverflowAPI:
    BASE_URL = "https://api.eflow.team/v1"
    HEADERS = {"X-Eflow-API-Key": api_key}
    
    # Endpoints to implement:
    # GET /v1/affiliates/offers → list all active offers
    # GET /v1/affiliates/offers/{id} → offer detail + tracking URL
    # GET /v1/affiliates/offers/{id}/creatives → email creatives (HTML bodies)
    # GET /v1/networks/offers/{id}/suppression → suppression emails list
    
    # Tracking URL format with subs:
    # offer.tracking_url + ?sub1={mailer_id}&sub2={list_id}&sub3={process_id}
    # Sub params configured per network in affiliate_networks.sub_config
```

### Cake API
```python
class CakeAPI:
    # SOAP/REST hybrid
    # POST /api/1/offers.asmx/GetOffers → all offers
    # POST /api/1/creative.asmx/GetCreatives?offer_id=X → creatives
    # POST /api/1/suppression.asmx/GetSuppressionList?offer_id=X → suppression
    # Requires: domain (in website_url), api_key
```

### HitPath API  
```python
class HitPathAPI:
    # Requires: api_url (website_url), username (api_username), 
    #           password (api_password), company_name
    # POST /auth/login → get token
    # GET /campaigns → all offers
    # GET /campaigns/{id}/suppression → suppression list
```

---

## TEMPLATE TAG ENGINE

Implement `services/tags.py` supporting ALL these tags:

### System Tags (square brackets, from screenshot 3)
- `[ip]` `[rdns]` `[ptr]` `[domain]` `[custom_domain]` `[route_domain]` `[static_domain]`
- `[server]` `[smtp_user]` `[email_id]` `[email]` `[first_name]` `[last_name]`
- `[return_path]` `[from_name]` `[subject]` `[mail_date]` `[message_id]`
- `[negative]` `[placeholder1]`...`[placeholderN]` `[auto_reply_mailbox]`
- `[LinksPlaceholder]` (rotated round-robin from links list)

### Random Tags (per-email, curly braces — from snd.py)
- `{a_N}` `{al_N}` `{au_N}` `{an_N}` `{anl_N}` `{anu_N}` `{n_N}`

### Fixed Random Tags (per-campaign-run, square brackets — from snd.py)
- `[a_N]` `[al_N]` `[au_N]` `[an_N]` `[anl_N]` `[anu_N]` `[n_N]`

### Unique Random Tags (from screenshot 3)
- `[ua_N]` `[ual_N]` `[uau_N]` `[uan_N]` `[uanl_N]` `[uanu_N]` `[un_N]`
- `[uhu_N]` `[uhl_N]` — hex variants
- Range variant: `[uan_5_15]` → random length between 5-15

### Link Tags (from screenshot 3)
- `[open]` `[url]` `[unsub]` `[optout]`
- `[short_open]` `[short_url]` `[short_unsub]` `[short_optout]`

### Encryption Tags (from screenshot 3)
- `[enc_b64_b]...[enc_b64_e]` → Base64
- `[enc_qp_b]...[enc_qp_e]` → Quoted Printable
- `[enc_hex_b]...[enc_hex_e]` → Hex Unicode

### Offer Data Tags (custom, this system)
- `{{offer.tracking_url}}` `{{offer.name}}` `{{offer.payout}}` `{{offer.preview_url}}`
- `{{offer.subject}}` `{{offer.from_name}}`
- `{{offer.data.FIELD_KEY}}` → dynamic from offer_data_fields table
- `{{account.email}}` `{{account.group}}` `{{campaign.id}}`
- `{{recipient.email}}` `{{recipient.name}}`

---

## PROXY INTEGRATION (Webshare GB)

```python
# services/proxy.py

WEBSHARE_API_KEY = settings.WEBSHARE_API_KEY
WEBSHARE_BASE = "https://proxy.webshare.io/api/v2"

async def get_fresh_gb_proxy(geo: str = "US") -> dict:
    """Fetch a residential GB proxy for given country from Webshare API"""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{WEBSHARE_BASE}/proxy/list/",
            headers={"Authorization": f"Token {WEBSHARE_API_KEY}"},
            params={"mode": "direct", "country_code__in": geo, "valid": True, "page_size": 1}
        )
        proxies = r.json()["results"]
        if proxies:
            p = proxies[0]
            return {
                "host": p["proxy_address"],
                "port": p["ports"]["socks5"],
                "user": p["username"],
                "pass": p["password"],
                "geo": p["country_code"]
            }
    return None

async def test_proxy(proxy: dict) -> dict:
    """Test proxy works + verify geo"""
    try:
        proxies = {"http://": f"socks5://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"}
        async with httpx.AsyncClient(proxies=proxies, timeout=10) as client:
            r = await client.get("http://ip-api.com/json")
            data = r.json()
            return {"working": True, "ip": data["query"], "geo": data["countryCode"]}
    except Exception as e:
        return {"working": False, "error": str(e)}

async def test_smtp_via_proxy(account: SenderAccount) -> dict:
    """Test Gmail SMTP auth through account's proxy"""
    # Use socks5 tunnel to smtp.gmail.com:587
    # Attempt EHLO + STARTTLS + AUTH
    # Return: {"working": True/False, "error": None/str}
```

---

## SEND ENGINE REQUIREMENTS

Extend `snd.py` with these capabilities:

1. **Proxy per account**: Each `SenderAccount` has its own proxy. DNS resolution AND SMTP connection go through that proxy using `PySocks` (`import socks`).

2. **Anti-detection**:
   - Random jitter on sleep: `sleep * (0.7 + random() * 0.6)`
   - Shuffle recipients before sending: `random.shuffle(recipients)`
   - Fresh Message-ID per email (already in snd.py)
   - Rotate X-Mailer header: random string
   - No more than 50 emails/hour per account
   - Random delay between accounts: 1-5 seconds

3. **Filter pipeline** (before any send):
   - Remove emails in `suppression_list` for the current `offer_id`
   - Remove emails/domains in global `blacklist`
   - Remove already-sent emails for this campaign
   - Log how many were filtered

4. **Script generation**: `services/script_gen.py` generates a complete, self-contained Python script that:
   - Embeds all recipients (base64-encoded JSON)
   - Embeds all accounts with their proxy configs
   - Embeds the processed header template and HTML body
   - Installs its own deps (`pip install -q dnspython PySocks`)
   - Obfuscates variable names with random 3-char prefix
   - Can be run directly in Google Cloud Shell: `python3 generated_script.py`

---

## GOOGLE CLOUD CONSOLE INTEGRATION

The "Send" button in the UI does NOT send emails directly from the web server. Instead:

1. **Generate** a standalone Python script with all data embedded
2. **Show** the script to the user with a copy button
3. **Link** to https://console.cloud.google.com/cloudshelleditor
4. **User** pastes and runs the script in Cloud Shell

This is the core architecture: the **web app is a configurator**, the **Cloud Shell is the executor**.

Why Cloud Shell:
- Free compute (Google provides it)
- Fast internet connection (Google infrastructure)
- No cost for the user
- Traffic exits through residential proxies → Google cannot detect it's Cloud Shell

---

## USER ROLES

### Admin
- Full access to everything
- Can create/manage Mailer accounts
- See all campaigns from all users
- Manage global blacklist
- Manage Webshare API key and proxy pool

### Mailer
- Can manage their own accounts, groups, recipient lists
- Can access shared affiliate networks and offers (read-only)
- Can create and run their own campaigns
- Can import suppression lists for offers they use
- Cannot see other users' data
- Cannot manage users or global settings

---

## FRONTEND PAGES

Build React 18 + TailwindCSS frontend with these pages:

### Login Page
- Email + password form
- JWT stored in httpOnly cookie
- Redirect to dashboard on success

### Dashboard
- Stats cards: total accounts (active/blocked), campaigns today, emails sent today
- Recent campaigns table with status
- Quick links: New Campaign, Check Accounts

### Accounts Page (`/accounts`)
- Table: email, type, group, proxy geo, status badge, last health check, daily sent
- Bulk import button (CSV textarea or file upload)
- Single add form
- "Test All" button → runs health checks in background
- Per-row: test, edit, rotate proxy, delete

### Groups Page (`/groups`)
- List of groups with account counts
- Create/rename/delete groups
- Drag accounts between groups

### Recipients Page (`/recipients`)
- List of recipient lists with counts
- Upload new list (drag-drop TXT/CSV)
- View list contents (paginated)
- Delete list

### Affiliate Networks Page (`/affiliates`)
Form fields EXACTLY as in screenshot 1:
- Affiliate Id, Network Name, Status dropdown, Website
- Username, Password
- Api Platform dropdown (None, Everflow, Cake, HitPath, Custom, Geniads)
- Network Id, Company Name, API Key
- API Username, API Password
- Sub 1 / Sub 2 / Sub 3 checkboxes: Mailer Id, Process Id, ISP Id, List Id, Email Id, Vmta Id

### Offers Page (`/offers`)
Form EXACTLY as in screenshot 2:
- Select Affiliate Network dropdown
- "Get All Offers" checkbox
- Offers Production IDs textarea (one per line)
- Max Number of Creatives input
- "Get All Creatives" checkbox
- API / Manual toggle button (top right)
- "Get Offers" button

Offers list table: name, network, payout, tracking URL, status, suppression count, actions

Offer detail: data fields CRUD table (key, value, type)

### Send Page (`/send`)
Multi-step wizard:
1. **Groups**: multi-select sender account groups (show count per group)
2. **Lists**: multi-select recipient lists (show count per list)
3. **Offer**: select affiliate network → select offer → preview offer data
4. **Compose**: header editor + HTML body editor (CodeMirror) + preview tab + links + negative content
5. **Config**: batch_size, sleep_between, max_workers, max_per_account, send_mode
6. **Review**: show totals → after filtering (suppression + blacklist) → accounts available → ETA
7. **Test**: send test email form → show result
8. **Launch**: generate script button → show script in code block → copy button → open Cloud Console link

### Blacklist Page (`/blacklist`)
- Global blacklist table: email/domain, reason, source, date
- Add single email/domain
- Bulk import textarea
- Suppression list tab: filter by offer

### Stats Page (`/stats`)
- Campaign selector
- Live stats: sent, failed, filtered, bounce rate
- Breakdown by domain (gmail.com X%, yahoo.com Y%, etc.)
- Per-account breakdown
- Send log table (email, status, account, mx used, timestamp)

---

## IMPLEMENTATION ORDER

Build in this exact order:

1. **Database**: All models + Alembic migrations
2. **Auth system**: JWT login, roles, middleware
3. **Accounts CRUD + Proxy service + Health check**
4. **Groups CRUD**
5. **Recipients upload + parsing**
6. **Affiliate networks CRUD + API clients (Everflow, Cake, HitPath)**
7. **Offers CRUD + import from API + data fields CRUD**
8. **Blacklist + Suppression CRUD**
9. **Tag engine** (all tags from SKILL_TAGS.md)
10. **Send engine** (proxy-aware MX + SMTP, extends snd.py)
11. **Script generator** (Cloud Console script)
12. **Campaign CRUD + send flow**
13. **Frontend**: React app with all pages

---

## SKILL REFERENCE FILES

The following skill files are in the `docs/` folder and MUST be used as reference:

- `SKILL_ACCOUNTS.md` — Full detail on Gmail/GSuite accounts + proxy setup
- `SKILL_AFFILIATES.md` — Everflow, Cake, HitPath API integration + all form fields
- `SKILL_TAGS.md` — Complete tag reference (from snd.py + screenshot 3)
- `SKILL_SEND.md` — Send flow, proxy tunnel code, anti-detection, script gen

---

## IMPORTANT CONSTRAINTS

1. **All passwords encrypted at rest** using Fernet symmetric encryption (not just hashed — they need to be decrypted for use)
2. **All DB queries async** using SQLAlchemy `AsyncSession`
3. **Celery tasks** for: health checks, large imports, send monitoring
4. **Rate limiting** on API endpoints using `slowapi`
5. **CORS** configured for frontend domain
6. **Environment variables** via `.env` file + Pydantic `BaseSettings`
7. **No hardcoded credentials** anywhere in code
8. **Pagination** on all list endpoints (default 50 per page)
9. **Soft delete** on sensitive data (campaigns, accounts) — never hard delete
10. **Audit log**: track who did what (login, send, import, delete)

---

## SKILLS FOLDER — HOW TO USE

All skill files are in the `skills/` folder. Before implementing any module, read the corresponding skill file first.

| Module to build | Read this skill first |
|----------------|----------------------|
| Sender accounts + proxy | `skills/SKILL_ACCOUNTS.md` |
| Affiliate networks (Everflow, Cake, HitPath) | `skills/SKILL_AFFILIATES.md` |
| Offers import + data fields + suppression | `skills/SKILL_OFFERS.md` |
| Template tag engine | `skills/SKILL_TAGS.md` |
| Send engine + MX + proxy tunnel | `skills/SKILL_SEND.md` |
| Webshare proxy API + health check | `skills/SKILL_PROXY.md` |
| Project structure + tech stack | `skills/README.md` |

Always consult the skill file before writing code for that module. The skills contain exact field names, API endpoints, DB columns, and code patterns that must match.
