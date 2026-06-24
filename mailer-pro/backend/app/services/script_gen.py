"""
Generates a self-contained Python script to run in Google Cloud Shell.

Two flavors:
  • BASIC  (mx_direct)  — faithful clone of the user's snd.py: account-less,
                          no proxy, no SMTP login. Resolves the recipient's MX
                          and delivers straight on port 25. This is what runs
                          cleanly from Google Cloud Shell.
  • PROXY  (smtp / mx_proxy) — routes each send through a sender account's
                          SOCKS5 proxy (Webshare / DataImpulse). Used when you
                          must send FROM authenticated Gmail accounts.
"""

import base64
import json
import random
import string


def _random_prefix(length: int = 3) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def generate_campaign_script(campaign, accounts: list[dict], recipients: list[dict]) -> str:
    """Dispatch by send_mode. Default (mx_direct) → basic snd.py clone."""
    mode = (campaign.send_mode or "mx_direct").lower()
    if mode in ("smtp", "mx_proxy", "gmail_api") and accounts:
        return _generate_proxy_script(campaign, accounts, recipients)
    return _generate_basic_script(campaign, recipients)


# ══════════════════════════════════════════════════════════════════════════════
# BASIC — snd.py clone (no accounts, no proxy, MX-direct)
# ══════════════════════════════════════════════════════════════════════════════
def _generate_basic_script(campaign, recipients: list[dict]) -> str:
    pfx = _random_prefix()

    recipients_b64 = base64.b64encode(json.dumps(recipients).encode()).decode()
    header_b64 = base64.b64encode((campaign.header_template or "").encode()).decode()
    body_b64 = base64.b64encode((campaign.body_html or "").encode()).decode()
    negative_b64 = base64.b64encode((campaign.negative_content or "").encode()).decode()
    links_b64 = base64.b64encode(json.dumps(campaign.links or []).encode()).decode()

    return f'''#!/usr/bin/env python3
# MailerPro — Campaign #{campaign.id}: {campaign.name}
# Basic MX-direct sender (snd.py style). Run in Google Cloud Shell:
#     python3 script.py
# No proxy, no SMTP login, no Gmail API — delivers straight to recipient MX.

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "dnspython"])

import smtplib, dns.resolver
import uuid, random, string, re, time, datetime, email.utils
import base64, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Embedded data ─────────────────────────────────────────────────────────────
{pfx}_recipients = json.loads(base64.b64decode("{recipients_b64}"))
{pfx}_header = base64.b64decode("{header_b64}").decode()
{pfx}_body   = base64.b64decode("{body_b64}").decode()
{pfx}_negative = base64.b64decode("{negative_b64}").decode()
{pfx}_links  = json.loads(base64.b64decode("{links_b64}"))

# ── Configuration (matches snd.py) ────────────────────────────────────────────
BATCH_SIZE = {campaign.batch_size}
MAX_WORKERS = {campaign.max_workers}
SLEEP_BETWEEN_BATCHES = {campaign.sleep_between}

fixed_random_values = {{}}
link_index = [0]

# ── Tag engine (snd.py compatible) ────────────────────────────────────────────
def generate_random_string(length, char_type):
    m = {{"a": string.ascii_letters, "al": string.ascii_lowercase,
          "au": string.ascii_uppercase, "an": string.ascii_letters + string.digits,
          "anl": string.ascii_lowercase + string.digits,
          "anu": string.ascii_uppercase + string.digits, "n": string.digits}}
    return "".join(random.choices(m.get(char_type, string.ascii_letters), k=length))

def replace_tags(text, ctx=None):
    ctx = ctx or {{}}

    # Per-email random  {{a_5}}  {{n_3}}  — fresh each call
    pattern = r"\\{{(a|al|au|an|anl|anu|n)_(\\d+)\\}}"
    match = re.search(pattern, text)
    while match:
        ct, ls = match.groups()
        text = text[:match.start()] + generate_random_string(int(ls), ct) + text[match.end():]
        match = re.search(pattern, text)

    # [mail_date]
    text = re.sub(r"\\[mail_date\\]", datetime.date.today().strftime("%Y-%m-%d"), text)

    # Fixed random  [a_5]  — same value for the whole run
    pattern = r"\\[(a|al|au|an|anl|anu|n)_(\\d+)\\]"
    match = re.search(pattern, text)
    while match:
        ct, ls = match.groups()
        tag = match.group()
        if tag not in fixed_random_values:
            fixed_random_values[tag] = generate_random_string(int(ls), ct)
        text = text[:match.start()] + fixed_random_values[tag] + text[match.end():]
        match = re.search(pattern, text)

    # [LinksPlaceholder] — rotate through links
    if {pfx}_links:
        cur = {pfx}_links[link_index[0] % len({pfx}_links)]
        if "[LinksPlaceholder]" in text:
            text = text.replace("[LinksPlaceholder]", cur)
            link_index[0] += 1

    # [negative]
    text = text.replace("[negative]", {pfx}_negative)

    # Context tags  [email]  [first_name]
    for k, v in ctx.items():
        text = text.replace(f"[{{k}}]", str(v))

    return text

def process_header(content, ctx):
    headers = {{}}
    for line in replace_tags(content, ctx).splitlines():
        if not line.strip():
            continue
        if line.startswith("From:"):
            em = re.search(r"<([^>]+)>", line)
            nm = re.search(r"From:\\s*([^<]+)", line)
            if em: headers["from_email"] = em.group(1).strip()
            if nm: headers["from_name"] = nm.group(1).strip()
        elif line.startswith("Subject:"):
            sm = re.search(r"Subject:\\s*(.*)", line)
            if sm: headers["subject"] = sm.group(1).strip()
        elif ":" in line:
            n, v = line.split(":", 1)
            headers[n.strip()] = v.strip()
    return headers

# ── MX direct (no proxy, no login) ─────────────────────────────────────────────
def get_mx_records(domain):
    records = dns.resolver.resolve(domain, "MX")
    return [str(r.exchange) for r in sorted(records, key=lambda r: r.preference)]

def send_email_via_mx(to_emails):
    if not to_emails:
        return
    domain = to_emails[0].split("@")[1]

    ctx = {{"email": to_emails[0], "first_name": to_emails[0].split("@")[0]}}
    headers = process_header({pfx}_header, ctx)
    from_email = headers.get("from_email", "")
    from_name = headers.get("from_name", "")
    subject = headers.get("subject", "")

    msg = MIMEMultipart()
    msg["Subject"] = replace_tags(subject, ctx)
    msg["From"] = f"{{from_name}} <{{from_email}}>"
    msg["To"] = from_email
    msg["Bcc"] = "; ".join(to_emails)
    for name, value in headers.items():
        if name.lower() not in ("from", "subject", "from_email", "from_name"):
            msg[name] = value
    msg["Message-ID"] = f"<{{uuid.uuid4()}}@{{domain}}>"
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(replace_tags({pfx}_body, ctx), "html"))

    for mx in get_mx_records(domain):
        try:
            with smtplib.SMTP(mx.rstrip("."), timeout=30) as server:
                server.sendmail(from_email, to_emails, msg.as_string())
                print(f"[SENT] {{len(to_emails)}} -> {{to_emails}} via {{mx}}")
                return
        except Exception as e:
            print(f"[WARN] {{mx}} failed: {{e}}")
    print(f"[FAIL] all MX failed for {{to_emails}}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    emails = [r["email"] for r in {pfx}_recipients if r.get("email")]
    random.shuffle(emails)
    batches = [emails[i:i + BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]
    print(f"Campaign #{campaign.id} | {{len(emails)}} recipients | {{len(batches)}} batches")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for batch in batches:
            futures.append(ex.submit(send_email_via_mx, batch))
            time.sleep(SLEEP_BETWEEN_BATCHES)
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"[EXCEPTION] {{e}}")

    print("\\n✓ All emails sent.")

if __name__ == "__main__":
    main()
'''


# ══════════════════════════════════════════════════════════════════════════════
# PROXY — per-account SOCKS5 (smtp / mx_proxy)
# ══════════════════════════════════════════════════════════════════════════════
def _generate_proxy_script(campaign, accounts: list[dict], recipients: list[dict]) -> str:
    pfx = _random_prefix()

    recipients_b64 = base64.b64encode(json.dumps(recipients).encode()).decode()
    accounts_b64 = base64.b64encode(json.dumps(accounts).encode()).decode()
    header_b64 = base64.b64encode((campaign.header_template or "").encode()).decode()
    body_b64 = base64.b64encode((campaign.body_html or "").encode()).decode()
    negative_b64 = base64.b64encode((campaign.negative_content or "").encode()).decode()
    links_b64 = base64.b64encode(json.dumps(campaign.links or []).encode()).decode()

    return f'''#!/usr/bin/env python3
# MailerPro — Campaign #{campaign.id}: {campaign.name}
# Proxy sender — routes each account through its SOCKS5 proxy.
# Run in Google Cloud Shell: python3 script.py

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "dnspython", "PySocks"])

import smtplib, dns.resolver, socks, socket, importlib
import uuid, random, string, email.utils, re, time, datetime
import base64, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed

{pfx}_r = json.loads(base64.b64decode("{recipients_b64}"))
{pfx}_a = json.loads(base64.b64decode("{accounts_b64}"))
{pfx}_h = base64.b64decode("{header_b64}").decode()
{pfx}_b = base64.b64decode("{body_b64}").decode()
{pfx}_n = base64.b64decode("{negative_b64}").decode()
{pfx}_l = json.loads(base64.b64decode("{links_b64}"))

BATCH_SIZE = {campaign.batch_size}
SLEEP_BETWEEN = {campaign.sleep_between}
MAX_WORKERS = {campaign.max_workers}
SEND_MODE = "{campaign.send_mode}"

_fixed = {{}}
_link_idx = [0]

def _rand(n, t):
    m = {{"a": string.ascii_letters, "al": string.ascii_lowercase,
          "au": string.ascii_uppercase, "an": string.ascii_letters+string.digits,
          "anl": string.ascii_lowercase+string.digits,
          "anu": string.ascii_uppercase+string.digits, "n": string.digits}}
    return "".join(random.choices(m.get(t, string.ascii_letters), k=n))

def rtags(text, ctx=None):
    ctx = ctx or {{}}
    text = re.sub(r"\\{{(a|al|au|an|anl|anu|n)_(\\d+)\\}}",
        lambda m: _rand(int(m.group(2)), m.group(1)), text)
    text = re.sub(r"\\[mail_date\\]", datetime.date.today().strftime("%Y-%m-%d"), text)
    def fix(m):
        tag, t, n = m.group(0), m.group(1), int(m.group(2))
        _fixed.setdefault(tag, _rand(n, t))
        return _fixed[tag]
    text = re.sub(r"\\[(a|al|au|an|anl|anu|n)_(\\d+)\\]", fix, text)
    if {pfx}_l:
        def rotlink(m):
            link = {pfx}_l[_link_idx[0] % len({pfx}_l)]
            _link_idx[0] += 1
            return link
        text = re.sub(r"\\[LinksPlaceholder\\]", rotlink, text)
    text = text.replace("[negative]", {pfx}_n)
    for k, v in ctx.items():
        text = text.replace(f"[{{k}}]", str(v))
    return text

def parse_header(hdr, ctx):
    h = {{}}
    for line in rtags(hdr, ctx).splitlines():
        if line.startswith("From:"):
            em = re.search(r"<([^>]+)>", line); nm = re.search(r"From:\\s*([^<\\n]+)", line)
            if em: h["from_email"] = em.group(1).strip()
            if nm: h["from_name"] = nm.group(1).strip().rstrip(" <")
        elif line.startswith("Subject:"):
            sm = re.search(r"Subject:\\s*(.*)", line)
            if sm: h["subject"] = sm.group(1).strip()
        elif ":" in line:
            n, v = line.split(":", 1); h[n.strip()] = v.strip()
    return h

def mx_via_proxy(domain, proxy):
    socks.set_default_proxy(socks.SOCKS5, proxy["proxy_host"], proxy["proxy_port"],
        username=proxy.get("proxy_user"), password=proxy.get("proxy_pass"))
    socket.socket = socks.socksocket
    try:
        r = dns.resolver.Resolver(); r.nameservers = ["8.8.8.8", "1.1.1.1"]
        recs = r.resolve(domain, "MX")
        return [str(x.exchange) for x in sorted(recs, key=lambda x: x.preference)]
    finally:
        importlib.reload(socket)

def smtp_via_proxy(mx, proxy):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, proxy["proxy_host"], proxy["proxy_port"],
        username=proxy.get("proxy_user"), password=proxy.get("proxy_pass"))
    s.settimeout(20); s.connect((mx.rstrip("."), 25))
    srv = smtplib.SMTP(); srv.sock = s; srv.file = s.makefile("rb")
    srv._get_reply(); srv.ehlo(); return srv

def smtp_gmail_proxy(account):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, account["proxy_host"], account["proxy_port"],
        username=account.get("proxy_user"), password=account.get("proxy_pass"))
    s.settimeout(15); s.connect(("smtp.gmail.com", 587))
    srv = smtplib.SMTP(); srv.sock = s; srv.file = s.makefile("rb")
    srv._get_reply(); srv.ehlo(); srv.starttls(); srv.ehlo()
    srv.login(account["email"], account["password"]); return srv

def send_batch(batch, account):
    ctx = {{"email": batch[0].get("email",""), "first_name": (batch[0].get("name") or batch[0].get("email","").split("@")[0])}}
    h = parse_header({pfx}_h, ctx)
    from_email = h.get("from_email", account["email"])
    from_name = h.get("from_name", "Support")
    subject = h.get("subject", "Hello")
    for recipient in batch:
        ctx["email"] = recipient.get("email","")
        ctx["first_name"] = recipient.get("name") or ctx["email"].split("@")[0]
        body = rtags({pfx}_b, ctx)
        to_email = recipient.get("email",""); domain = to_email.split("@")[1] if "@" in to_email else ""
        msg = MIMEMultipart()
        msg["Subject"] = rtags(subject, ctx)
        msg["From"] = f"{{rtags(from_name, ctx)}} <{{rtags(from_email, ctx)}}>"
        msg["To"] = to_email
        msg["Message-ID"] = f"<{{uuid.uuid4()}}@{{domain}}>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.attach(MIMEText(body, "html"))
        try:
            if SEND_MODE == "smtp":
                srv = smtp_gmail_proxy(account)
                srv.sendmail(rtags(from_email, ctx), [to_email], msg.as_string()); srv.quit()
                print(f"[SENT] {{to_email}} via smtp.gmail.com")
            else:
                sent = False
                for mx in mx_via_proxy(domain, account):
                    try:
                        srv = smtp_via_proxy(mx, account)
                        srv.sendmail(rtags(from_email, ctx), [to_email], msg.as_string()); srv.quit()
                        print(f"[SENT] {{to_email}} via {{mx}}"); sent = True; break
                    except Exception as e:
                        print(f"[WARN] MX {{mx}} failed: {{e}}")
                if not sent:
                    print(f"[FAIL] {{to_email}} all MX failed")
        except Exception as e:
            print(f"[ERROR] {{to_email}}: {{e}}")
        time.sleep(SLEEP_BETWEEN * (0.7 + random.random() * 0.6))

def main():
    recipients = {pfx}_r[:]; random.shuffle(recipients)
    pool = [a for a in {pfx}_a if a.get("proxy_host")]
    if not pool:
        print("ERROR: No accounts with proxy config"); return
    batches = [recipients[i:i+BATCH_SIZE] for i in range(0, len(recipients), BATCH_SIZE)]
    print(f"Campaign #{campaign.id} | {{len(recipients)}} recipients | {{len(pool)}} accounts | {{len(batches)}} batches")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(send_batch, b, pool[i % len(pool)]) for i, b in enumerate(batches)]
        for f in as_completed(futures):
            try: f.result()
            except Exception as e: print(f"[EXCEPTION] {{e}}")
    print("\\n✓ All done.")

if __name__ == "__main__":
    main()
'''
