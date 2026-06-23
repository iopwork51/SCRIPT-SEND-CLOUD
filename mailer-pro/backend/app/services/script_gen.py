"""
Generates a self-contained Python script to run in Google Cloud Shell.
The script extends snd.py with proxy-per-account, anti-detection,
and embeds all recipients and account data.
"""

import base64
import json
import random
import string


def _random_prefix(length: int = 3) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def generate_campaign_script(campaign, accounts: list[dict], recipients: list[dict]) -> str:
    pfx = _random_prefix()

    # Encode data as base64 JSON to obfuscate
    recipients_b64 = base64.b64encode(json.dumps(recipients).encode()).decode()
    accounts_b64 = base64.b64encode(json.dumps(accounts).encode()).decode()
    header_b64 = base64.b64encode((campaign.header_template or "").encode()).decode()
    body_b64 = base64.b64encode((campaign.body_html or "").encode()).decode()
    negative_b64 = base64.b64encode((campaign.negative_content or "").encode()).decode()
    links_b64 = base64.b64encode(json.dumps(campaign.links or []).encode()).decode()

    script = f'''#!/usr/bin/env python3
# MailerPro generated script — Campaign #{campaign.id}: {campaign.name}
# Run in Google Cloud Shell: python3 script.py

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
    "dnspython", "PySocks"])

import smtplib, dns.resolver, socks, socket, importlib
import uuid, random, string, email.utils, re, time, datetime
import base64, json, quopri
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Embedded data ─────────────────────────────────────────────────────────────
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

# ── Tag engine ────────────────────────────────────────────────────────────────
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
    # Per-email random
    text = re.sub(r\'\\{{(a|al|au|an|anl|anu|n)_(\\d+)\\}}\',
        lambda m: _rand(int(m.group(2)), m.group(1)), text)
    # mail_date
    text = re.sub(r\'\\[mail_date\\]\', datetime.date.today().strftime(\'%Y-%m-%d\'), text)
    # Fixed random
    def fix(m):
        tag, t, n = m.group(0), m.group(1), int(m.group(2))
        _fixed.setdefault(tag, _rand(n, t))
        return _fixed[tag]
    text = re.sub(r\'\\[(a|al|au|an|anl|anu|n)_(\\d+)\\]\', fix, text)
    # Unique random
    def uniq(m):
        t, n1 = m.group(1), int(m.group(2))
        n2 = int(m.group(3)) if m.group(3) else n1
        n = random.randint(n1, n2)
        tm = {{"ua":"a","ual":"al","uau":"au","uan":"an","uanl":"anl","uanu":"anu","un":"n"}}
        if t in ("uhu","uhl"):
            h = "".join(random.choices("0123456789abcdef", k=n))
            return h.upper() if t=="uhu" else h
        return _rand(n, tm.get(t, "an"))
    text = re.sub(r\'\\[(ua|ual|uau|uan|uanl|uanu|un|uhu|uhl)_(\\d+)(?:_(\\d+))?\\]\', uniq, text)
    # Links
    if {pfx}_l:
        def rotlink(m):
            link = {pfx}_l[_link_idx[0] % len({pfx}_l)]
            _link_idx[0] += 1
            return link
        text = re.sub(r\'\\[LinksPlaceholder\\]\', rotlink, text)
    # Negative
    text = text.replace(\'[negative]\', {pfx}_n)
    # Context tags
    for k, v in ctx.items():
        text = text.replace(f\'[{{k}}]\', str(v))
    return text

def parse_header(hdr, ctx):
    h = {{}}
    for line in rtags(hdr, ctx).splitlines():
        if line.startswith("From:"):
            em = re.search(r\'<([^>]+)>\', line)
            nm = re.search(r\'From:\\s*([^<\\n]+)\', line)
            if em: h["from_email"] = em.group(1).strip()
            if nm: h["from_name"] = nm.group(1).strip().rstrip(" <")
        elif line.startswith("Subject:"):
            sm = re.search(r\'Subject:\\s*(.*)\', line)
            if sm: h["subject"] = sm.group(1).strip()
        elif ":" in line:
            n, v = line.split(":", 1)
            h[n.strip()] = v.strip()
    return h

# ── MX via proxy ──────────────────────────────────────────────────────────────
def mx_via_proxy(domain, proxy):
    socks.set_default_proxy(socks.SOCKS5, proxy["proxy_host"], proxy["proxy_port"],
        username=proxy.get("proxy_user"), password=proxy.get("proxy_pass"))
    socket.socket = socks.socksocket
    try:
        r = dns.resolver.Resolver()
        r.nameservers = ["8.8.8.8", "1.1.1.1"]
        recs = r.resolve(domain, "MX")
        return [str(x.exchange) for x in sorted(recs, key=lambda x: x.preference)]
    finally:
        importlib.reload(socket)

def smtp_via_proxy(mx, proxy):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, proxy["proxy_host"], proxy["proxy_port"],
        username=proxy.get("proxy_user"), password=proxy.get("proxy_pass"))
    s.settimeout(20)
    s.connect((mx.rstrip("."), 25))
    srv = smtplib.SMTP()
    srv.sock = s
    srv.file = s.makefile("rb")
    srv._get_reply()
    srv.ehlo()
    return srv

def smtp_gmail_proxy(account, proxy):
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, proxy["proxy_host"], proxy["proxy_port"],
        username=proxy.get("proxy_user"), password=proxy.get("proxy_pass"))
    s.settimeout(15)
    s.connect(("smtp.gmail.com", 587))
    srv = smtplib.SMTP()
    srv.sock = s
    srv.file = s.makefile("rb")
    srv._get_reply()
    srv.ehlo()
    srv.starttls()
    srv.ehlo()
    srv.login(account["email"], account["password"])
    return srv

# ── Send one batch ─────────────────────────────────────────────────────────────
def send_batch(batch, account):
    proxy = account
    ctx = {{"email": batch[0].get("email",""), "first_name": (batch[0].get("name") or batch[0].get("email","").split("@")[0])}}
    h = parse_header({pfx}_h, ctx)
    from_email = h.get("from_email", account["email"])
    from_name = h.get("from_name", "Support")
    subject = h.get("subject", "Hello")

    for recipient in batch:
        ctx["email"] = recipient.get("email","")
        ctx["first_name"] = recipient.get("name") or ctx["email"].split("@")[0]
        body = rtags({pfx}_b, ctx)
        to_email = recipient.get("email","")
        domain = to_email.split("@")[1] if "@" in to_email else ""

        msg = MIMEMultipart()
        msg["Subject"] = rtags(subject, ctx)
        msg["From"] = f"{{rtags(from_name, ctx)}} <{{rtags(from_email, ctx)}}>"
        msg["To"] = to_email
        msg["Message-ID"] = f"<{{uuid.uuid4()}}@{{domain}}>"
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["X-Mailer"] = "".join(random.choices(string.ascii_letters+string.digits, k=12))
        msg.attach(MIMEText(body, "html"))

        jitter = SLEEP_BETWEEN * (0.7 + random.random() * 0.6)

        try:
            if SEND_MODE == "smtp":
                srv = smtp_gmail_proxy(account, proxy)
                srv.sendmail(rtags(from_email, ctx), [to_email], msg.as_string())
                srv.quit()
                print(f"[SENT] {{to_email}} via smtp.gmail.com")
            else:
                mx_list = mx_via_proxy(domain, proxy)
                sent = False
                for mx in mx_list:
                    try:
                        srv = smtp_via_proxy(mx, proxy)
                        srv.sendmail(rtags(from_email, ctx), [to_email], msg.as_string())
                        srv.quit()
                        print(f"[SENT] {{to_email}} via {{mx}}")
                        sent = True
                        break
                    except Exception as e:
                        print(f"[WARN] MX {{mx}} failed: {{e}}")
                if not sent:
                    print(f"[FAIL] {{to_email}} all MX failed")
        except Exception as e:
            print(f"[ERROR] {{to_email}}: {{e}}")

        time.sleep(jitter)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    recipients = {pfx}_r[:]
    random.shuffle(recipients)
    accounts = {pfx}_a[:]

    batches = [recipients[i:i+BATCH_SIZE] for i in range(0, len(recipients), BATCH_SIZE)]
    print(f"Campaign #{campaign.id} | {{len(recipients)}} recipients | {{len(accounts)}} accounts | {{len(batches)}} batches")

    account_pool = [a for a in accounts if a.get("proxy_host")]
    if not account_pool:
        print("ERROR: No accounts with proxy config")
        return

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for i, batch in enumerate(batches):
            account = account_pool[i % len(account_pool)]
            futures.append(ex.submit(send_batch, batch, account))

        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f"[EXCEPTION] {{e}}")

    print("\\n✓ All done.")

if __name__ == "__main__":
    main()
'''
    return script
