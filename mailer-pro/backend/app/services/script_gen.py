"""
Generates a self-contained Python script to run in Google Cloud Shell.

Tag engine (VuGex-compatible):
  Random tags          [a_12]  / ranged [a_5_15]   -> fresh value each occurrence
  Unique random tags   [ua_12] / ranged [ua_5_15]  -> one value per email (cached)
  Types: a al au an anl anu n hu hl   (hu/hl = hex)  and the u-prefixed unique forms
  Curly {a_5}          -> per-occurrence random (legacy)
  [mail_date]          -> today's date
  [PlaceholderN]       -> rotates through placeholder set N's lines
  [LinksPlaceholder]   -> rotates through the links list
  [negative]           -> Negative/Filler content
  [email] [first_name] [domain] -> context

Two flavors: BASIC (mx_direct, no account/proxy) and PROXY (smtp / mx_proxy).
"""

import base64
import json
import random
import string


def _b64(obj) -> str:
    if isinstance(obj, (dict, list)):
        return base64.b64encode(json.dumps(obj).encode()).decode()
    return base64.b64encode((obj or "").encode()).decode()


# ── Shared tag engine (plain Python, injected verbatim into the script) ─────────
_ENGINE_SRC = r'''
import re, random, string, datetime, uuid, email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_CHARS = {
    "a": string.ascii_letters, "al": string.ascii_lowercase, "au": string.ascii_uppercase,
    "an": string.ascii_letters + string.digits,
    "anl": string.ascii_lowercase + string.digits,
    "anu": string.ascii_uppercase + string.digits,
    "n": string.digits,
}
def _rs(n, t):
    return "".join(random.choices(_CHARS.get(t, string.ascii_letters), k=n))
def _hx(n, upper):
    h = "".join(random.choices("0123456789abcdef", k=n))
    return h.upper() if upper else h

# rotation counters per placeholder set
PH_COUNTER = [0] * len(PLACEHOLDERS)

def render(text, ctx, uniq):
    # 1. Unique random [uX_n] / [uX_n_m]  -> cached per email (same value reused)
    def U(m):
        key = m.group(0)
        if key in uniq:
            return uniq[key]
        t, n1, n2 = m.group(1), int(m.group(2)), m.group(3)
        L = random.randint(n1, int(n2)) if n2 else n1
        if t == "uhu": v = _hx(L, True)
        elif t == "uhl": v = _hx(L, False)
        else:
            v = _rs(L, {"ua":"a","ual":"al","uau":"au","uan":"an","uanl":"anl","uanu":"anu","un":"n"}[t])
        uniq[key] = v
        return v
    text = re.sub(r"\[(uanl|uanu|ual|uau|uan|ua|uhu|uhl|un)_(\d+)(?:_(\d+))?\]", U, text)

    # 2. Random [X_n] / [X_n_m]  -> fresh each occurrence
    def R(m):
        t, n1, n2 = m.group(1), int(m.group(2)), m.group(3)
        L = random.randint(n1, int(n2)) if n2 else n1
        if t == "hu": return _hx(L, True)
        if t == "hl": return _hx(L, False)
        return _rs(L, t)
    text = re.sub(r"\[(anl|anu|al|au|an|a|hu|hl|n)_(\d+)(?:_(\d+))?\]", R, text)

    # 3. Curly per-occurrence {X_n}
    text = re.sub(r"\{(a|al|au|an|anl|anu|n)_(\d+)\}", lambda m: _rs(int(m.group(2)), m.group(1)), text)

    # 4. [mail_date]
    text = re.sub(r"\[mail_date\]", datetime.date.today().strftime("%Y-%m-%d"), text)

    # 5. Placeholders [PlaceholderN]
    def PH(m):
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(PLACEHOLDERS):
            s = PLACEHOLDERS[idx]
            lines = s.get("lines") or []
            if not lines:
                return ""
            if s.get("combination"):
                return random.choice(lines)
            rot = max(1, int(s.get("rotation", 1)))
            i = (PH_COUNTER[idx] // rot) % len(lines)
            PH_COUNTER[idx] += 1
            return lines[i]
        return ""
    text = re.sub(r"\[Placeholder(\d+)\]", PH, text)

    # 6. [LinksPlaceholder]
    if LINKS:
        def L_(m):
            v = LINKS[LINK_IDX[0] % len(LINKS)]
            LINK_IDX[0] += 1
            return v
        text = re.sub(r"\[LinksPlaceholder\]", L_, text)

    # 7. [negative]
    text = text.replace("[negative]", NEGATIVE)

    # 8. context tags
    for k, v in ctx.items():
        text = text.replace("[" + k + "]", str(v))
    return text

def parse_header(hdr_text):
    h = {}
    for line in hdr_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("From:"):
            em = re.search(r"<([^>]+)>", line)
            nm = re.search(r"From:\s*([^<]+)", line)
            if em: h["from_email"] = em.group(1).strip()
            if nm: h["from_name"] = nm.group(1).strip()
        elif line.startswith("Subject:"):
            sm = re.search(r"Subject:\s*(.*)", line)
            if sm: h["subject"] = sm.group(1).strip()
        elif ":" in line:
            n, v = line.split(":", 1)
            h[n.strip()] = v.strip()
    return h
'''


def _data_block(campaign, recipients, placeholders, with_accounts=None) -> str:
    lines = [
        f'RECIPIENTS = json.loads(base64.b64decode("{_b64(recipients)}"))',
        f'HEADER = base64.b64decode("{_b64(campaign.header_template)}").decode()',
        f'BODY = base64.b64decode("{_b64(campaign.body_html)}").decode()',
        f'NEGATIVE = base64.b64decode("{_b64(campaign.negative_content)}").decode()',
        f'LINKS = json.loads(base64.b64decode("{_b64(campaign.links or [])}"))',
        f'PLACEHOLDERS = json.loads(base64.b64decode("{_b64(placeholders or [])}"))',
        'LINK_IDX = [0]',
        f'BATCH_SIZE = {campaign.batch_size}',
        f'MAX_WORKERS = {campaign.max_workers}',
        f'SLEEP_BETWEEN = {campaign.sleep_between}',
        f'SEND_MODE = "{campaign.send_mode}"',
    ]
    if with_accounts is not None:
        lines.append(f'ACCOUNTS = json.loads(base64.b64decode("{_b64(with_accounts)}"))')
    return "\n".join(lines)


def generate_campaign_script(campaign, accounts, recipients, placeholders=None):
    mode = (campaign.send_mode or "mx_direct").lower()
    if mode in ("smtp", "mx_proxy", "gmail_api") and accounts:
        return _generate_proxy_script(campaign, accounts, recipients, placeholders)
    return _generate_basic_script(campaign, recipients, placeholders)


# ══════════════════════════════════════════════════════════════════════════════
# BASIC — snd.py clone (no accounts, no proxy, MX-direct)
# ══════════════════════════════════════════════════════════════════════════════
def _generate_basic_script(campaign, recipients, placeholders=None) -> str:
    header = f'''#!/usr/bin/env python3
# MailerPro — Campaign #{campaign.id}: {campaign.name}
# Basic MX-direct sender (snd.py style). Run in Google Cloud Shell: python3 script.py
# No proxy, no SMTP login, no Gmail API — delivers straight to recipient MX.

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "dnspython"])

import smtplib, dns.resolver, base64, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

'''

    data = _data_block(campaign, recipients, placeholders)

    main = '''

def get_mx(domain):
    recs = dns.resolver.resolve(domain, "MX")
    return [str(r.exchange) for r in sorted(recs, key=lambda r: r.preference)]

def send_batch(batch):
    if not batch:
        return
    uniq = {}
    first = batch[0]
    ctx = {"email": first, "first_name": first.split("@")[0] if "@" in first else first}
    hdr = parse_header(render(HEADER, ctx, uniq))
    from_email = hdr.get("from_email", "")
    from_name = hdr.get("from_name", "")
    subject = hdr.get("subject", "")
    body = render(BODY, ctx, uniq)
    domain = first.split("@")[1] if "@" in first else ""

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = from_email
    msg["Bcc"] = "; ".join(batch)
    for k, v in hdr.items():
        if k.lower() not in ("from", "subject", "from_email", "from_name"):
            msg[k] = v
    msg["Message-ID"] = f"<{uuid.uuid4()}@{domain}>"
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(body, "html"))

    for mx in get_mx(domain):
        try:
            with smtplib.SMTP(mx.rstrip("."), timeout=30) as s:
                s.sendmail(from_email, batch, msg.as_string())
                print(f"[SENT] {len(batch)} -> {batch} via {mx}")
                return
        except Exception as e:
            print(f"[WARN] {mx} failed: {e}")
    print(f"[FAIL] all MX failed for {batch}")

def main():
    emails = [r["email"] for r in RECIPIENTS if r.get("email")]
    random.shuffle(emails)
    batches = [emails[i:i+BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]
    print(f"{len(emails)} recipients | {len(batches)} batches")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for b in batches:
            futures.append(ex.submit(send_batch, b))
            time.sleep(SLEEP_BETWEEN)
        for f in as_completed(futures):
            try: f.result()
            except Exception as e: print(f"[EXCEPTION] {e}")
    print("\\n✓ All emails sent.")

if __name__ == "__main__":
    main()
'''
    return header + data + "\n" + _ENGINE_SRC + main


# ══════════════════════════════════════════════════════════════════════════════
# PROXY — per-account SOCKS5 (smtp / mx_proxy)
# ══════════════════════════════════════════════════════════════════════════════
def _generate_proxy_script(campaign, accounts, recipients, placeholders=None) -> str:
    header = f'''#!/usr/bin/env python3
# MailerPro — Campaign #{campaign.id}: {campaign.name}
# Proxy sender — routes each account through its SOCKS5 proxy. Run: python3 script.py

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "dnspython", "PySocks"])

import smtplib, dns.resolver, socks, socket, importlib, base64, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed

'''

    data = _data_block(campaign, recipients, placeholders, with_accounts=accounts)

    main = '''

def mx_via_proxy(domain, p):
    socks.set_default_proxy(socks.SOCKS5, p["proxy_host"], p["proxy_port"],
        username=p.get("proxy_user"), password=p.get("proxy_pass"))
    socket.socket = socks.socksocket
    try:
        r = dns.resolver.Resolver(); r.nameservers = ["8.8.8.8", "1.1.1.1"]
        recs = r.resolve(domain, "MX")
        return [str(x.exchange) for x in sorted(recs, key=lambda x: x.preference)]
    finally:
        importlib.reload(socket)

def smtp_via_proxy(mx, p):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, p["proxy_host"], p["proxy_port"],
        username=p.get("proxy_user"), password=p.get("proxy_pass"))
    s.settimeout(20); s.connect((mx.rstrip("."), 25))
    srv = smtplib.SMTP(); srv.sock = s; srv.file = s.makefile("rb")
    srv._get_reply(); srv.ehlo(); return srv

def smtp_gmail_proxy(a):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, a["proxy_host"], a["proxy_port"],
        username=a.get("proxy_user"), password=a.get("proxy_pass"))
    s.settimeout(15); s.connect(("smtp.gmail.com", 587))
    srv = smtplib.SMTP(); srv.sock = s; srv.file = s.makefile("rb")
    srv._get_reply(); srv.ehlo(); srv.starttls(); srv.ehlo()
    srv.login(a["email"], a["password"]); return srv

def send_batch(batch, account):
    for recipient in batch:
        uniq = {}
        to_email = recipient.get("email", "")
        ctx = {"email": to_email, "first_name": recipient.get("name") or (to_email.split("@")[0] if "@" in to_email else to_email)}
        hdr = parse_header(render(HEADER, ctx, uniq))
        from_email = hdr.get("from_email", account["email"])
        from_name = hdr.get("from_name", "Support")
        subject = hdr.get("subject", "Hello")
        body = render(BODY, ctx, uniq)
        domain = to_email.split("@")[1] if "@" in to_email else ""

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        for k, v in hdr.items():
            if k.lower() not in ("from", "subject", "from_email", "from_name"):
                msg[k] = v
        msg["Message-ID"] = f"<{uuid.uuid4()}@{domain}>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg.attach(MIMEText(body, "html"))

        try:
            if SEND_MODE == "smtp":
                srv = smtp_gmail_proxy(account)
                srv.sendmail(from_email, [to_email], msg.as_string()); srv.quit()
                print(f"[SENT] {to_email} via smtp.gmail.com")
            else:
                sent = False
                for mx in mx_via_proxy(domain, account):
                    try:
                        srv = smtp_via_proxy(mx, account)
                        srv.sendmail(from_email, [to_email], msg.as_string()); srv.quit()
                        print(f"[SENT] {to_email} via {mx}"); sent = True; break
                    except Exception as e:
                        print(f"[WARN] MX {mx} failed: {e}")
                if not sent:
                    print(f"[FAIL] {to_email} all MX failed")
        except Exception as e:
            print(f"[ERROR] {to_email}: {e}")
        time.sleep(SLEEP_BETWEEN * (0.7 + random.random() * 0.6))

def main():
    recipients = RECIPIENTS[:]; random.shuffle(recipients)
    pool = [a for a in ACCOUNTS if a.get("proxy_host")]
    if not pool:
        print("ERROR: No accounts with proxy config"); return
    batches = [recipients[i:i+BATCH_SIZE] for i in range(0, len(recipients), BATCH_SIZE)]
    print(f"{len(recipients)} recipients | {len(pool)} accounts | {len(batches)} batches")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(send_batch, b, pool[i % len(pool)]) for i, b in enumerate(batches)]
        for f in as_completed(futures):
            try: f.result()
            except Exception as e: print(f"[EXCEPTION] {e}")
    print("\\n✓ All done.")

if __name__ == "__main__":
    main()
'''
    return header + data + "\n" + _ENGINE_SRC + main
