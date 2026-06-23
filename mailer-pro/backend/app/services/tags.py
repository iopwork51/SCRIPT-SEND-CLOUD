"""
Template tag engine — supports all tags from SKILL_TAGS.md and snd.py.
Processing order:
  1. Per-email random tags {type_N}
  2. [mail_date]
  3. Fixed-per-run random tags [type_N]  (cached in fixed_random_values)
  4. Unique random tags [ua_N], [uan_N], etc. (new value every occurrence)
  5. [LinksPlaceholder] (round-robin)
  6. [negative]
  7. Encryption tags [enc_b64_b]...[enc_b64_e] etc.
  8. System / context tags [email], [first_name], {{offer.X}} etc.
"""

import re
import random
import string
import datetime
import base64
import quopri
from typing import Optional


def _rand(length: int, char_type: str) -> str:
    char_map = {
        "a": string.ascii_letters,
        "al": string.ascii_lowercase,
        "au": string.ascii_uppercase,
        "an": string.ascii_letters + string.digits,
        "anl": string.ascii_lowercase + string.digits,
        "anu": string.ascii_uppercase + string.digits,
        "n": string.digits,
    }
    pool = char_map.get(char_type, string.ascii_letters)
    return "".join(random.choices(pool, k=length))


def _rand_hex(length: int, upper: bool = True) -> str:
    raw = "".join(random.choices("0123456789abcdef", k=length))
    return raw.upper() if upper else raw


def replace_tags(
    text: str,
    context: dict | None = None,
    fixed_random_values: dict | None = None,
    links: list[str] | None = None,
    link_index_ref: list[int] | None = None,  # mutable [index] to share across calls
    negative_content: str = "",
) -> str:
    if fixed_random_values is None:
        fixed_random_values = {}
    if context is None:
        context = {}
    if link_index_ref is None:
        link_index_ref = [0]

    # ── 1. Per-email random {type_N} ─────────────────────────────────────────
    def replace_per_email_random(m):
        char_type, length_str = m.group(1), m.group(2)
        return _rand(int(length_str), char_type)

    text = re.sub(r'\{(a|al|au|an|anl|anu|n)_(\d+)\}', replace_per_email_random, text)

    # ── 2. [mail_date] ───────────────────────────────────────────────────────
    text = re.sub(r'\[mail_date\]', datetime.date.today().strftime('%Y-%m-%d'), text)

    # ── 3. Fixed-per-run random [type_N] ─────────────────────────────────────
    def replace_fixed_random(m):
        tag = m.group(0)
        char_type, length_str = m.group(1), m.group(2)
        if tag not in fixed_random_values:
            fixed_random_values[tag] = _rand(int(length_str), char_type)
        return fixed_random_values[tag]

    text = re.sub(r'\[(a|al|au|an|anl|anu|n)_(\d+)\]', replace_fixed_random, text)

    # ── 4. Unique random tags (new value every call) ──────────────────────────
    def replace_unique(m):
        tag_type = m.group(1)   # ua, ual, uau, uan, uanl, uanu, un, uhu, uhl
        n1 = int(m.group(2))
        n2 = m.group(3)
        length = random.randint(n1, int(n2)) if n2 else n1

        type_map = {
            "ua": "a", "ual": "al", "uau": "au",
            "uan": "an", "uanl": "anl", "uanu": "anu",
            "un": "n",
        }
        if tag_type == "uhu":
            return _rand_hex(length, upper=True)
        if tag_type == "uhl":
            return _rand_hex(length, upper=False)
        return _rand(length, type_map.get(tag_type, "an"))

    text = re.sub(r'\[(ua|ual|uau|uan|uanl|uanu|un|uhu|uhl)_(\d+)(?:_(\d+))?\]', replace_unique, text)

    # ── 5. [LinksPlaceholder] ─────────────────────────────────────────────────
    if links:
        def rotate_link(m):
            link = links[link_index_ref[0] % len(links)]
            link_index_ref[0] += 1
            return link
        text = re.sub(r'\[LinksPlaceholder\]', rotate_link, text)

    # ── 6. [negative] ────────────────────────────────────────────────────────
    text = text.replace('[negative]', negative_content)

    # ── 7. Encryption tags ───────────────────────────────────────────────────
    def encrypt_b64(m):
        return base64.b64encode(m.group(1).encode()).decode()

    def encrypt_qp(m):
        return quopri.encodestring(m.group(1).encode()).decode()

    def encrypt_hex(m):
        return "".join(f"&#x{ord(c):04X};" for c in m.group(1))

    text = re.sub(r'\[enc_b64_b\](.*?)\[enc_b64_e\]', encrypt_b64, text, flags=re.DOTALL)
    text = re.sub(r'\[enc_qp_b\](.*?)\[enc_qp_e\]', encrypt_qp, text, flags=re.DOTALL)
    text = re.sub(r'\[enc_hex_b\](.*?)\[enc_hex_e\]', encrypt_hex, text, flags=re.DOTALL)

    # ── 8. Context / system tags ─────────────────────────────────────────────
    simple_tags = {
        "email": context.get("email", ""),
        "first_name": context.get("first_name", ""),
        "last_name": context.get("last_name", ""),
        "email_id": str(context.get("email_id", "")),
        "ip": context.get("ip", ""),
        "rdns": context.get("rdns", ""),
        "ptr": context.get("ptr", ""),
        "domain": context.get("domain", ""),
        "custom_domain": context.get("custom_domain", ""),
        "route_domain": context.get("route_domain", ""),
        "static_domain": context.get("static_domain", ""),
        "server": context.get("server", ""),
        "smtp_user": context.get("smtp_user", ""),
        "return_path": context.get("return_path", ""),
        "from_name": context.get("from_name", ""),
        "subject": context.get("subject", ""),
        "message_id": context.get("message_id", ""),
        "auto_reply_mailbox": context.get("auto_reply_mailbox", ""),
    }
    for tag, value in simple_tags.items():
        text = text.replace(f"[{tag}]", str(value))

    # Offer double-brace tags {{offer.X}}
    offer = context.get("offer", {})
    offer_data = context.get("offer_data", {})
    offer_tags = {
        "offer.tracking_url": offer.get("tracking_url", ""),
        "offer.name": offer.get("name", ""),
        "offer.payout": str(offer.get("payout", "")),
        "offer.preview_url": offer.get("preview_url", ""),
        "offer.subject": offer.get("suggested_subject", ""),
        "offer.from_name": offer.get("suggested_from_name", ""),
        "campaign.id": str(context.get("campaign_id", "")),
        "account.email": context.get("account_email", ""),
        "account.group": context.get("account_group", ""),
        "list.name": context.get("list_name", ""),
        "recipient.email": context.get("email", ""),
        "recipient.name": context.get("first_name", ""),
    }
    for tag, value in offer_tags.items():
        text = text.replace("{{" + tag + "}}", str(value))

    # {{offer.data.FIELD_KEY}}
    def replace_offer_data(m):
        key = m.group(1)
        return str(offer_data.get(key, ""))

    text = re.sub(r'\{\{offer\.data\.([^}]+)\}\}', replace_offer_data, text)

    return text


def process_header(header_text: str, context: dict, fixed_random_values: dict,
                   links: list[str], link_index_ref: list[int], negative_content: str) -> dict:
    processed = replace_tags(header_text, context, fixed_random_values, links, link_index_ref, negative_content)
    headers = {}
    for line in processed.splitlines():
        if line.startswith("From:"):
            email_match = re.search(r'<([^>]+)>', line)
            name_match = re.search(r'From:\s*([^<\n]+)', line)
            if email_match:
                headers["from_email"] = email_match.group(1).strip()
            if name_match:
                headers["from_name"] = name_match.group(1).strip().rstrip(" <")
        elif line.startswith("Subject:"):
            subject_match = re.search(r'Subject:\s*(.*)', line)
            if subject_match:
                headers["subject"] = subject_match.group(1).strip()
        elif ":" in line:
            name, value = line.split(":", 1)
            headers[name.strip()] = value.strip()
    return headers
