# SKILL: Template Tags Reference

Complete reference for all tags supported in email subjects, headers, and HTML body templates. Based on the system's tag engine (extended from `snd.py`).

---

## Tag Categories

### 1. Main Tags — System & Recipient Data

| Tag | Description | Example Output |
|-----|-------------|----------------|
| `[ip]` | The current sending server IP | `192.168.1.100` |
| `[rdns]` | The current IP's reverse DNS | `mail.domain.com` |
| `[ptr]` | The remote IP's PTR record | `ptr.host.net` |
| `[domain]` | The current IP's domain | `example.com` |
| `[custom_domain]` | The custom VMTA's domain | `send.mysite.com` |
| `[route_domain]` | The route VMTA's domain | `route.mysite.com` |
| `[static_domain]` | The static domain | `static.mysite.com` |
| `[server]` | Server name | `cloud-server-01` |
| `[smtp_user]` | SMTP username (SMTP process only) | `sender@gmail.com` |
| `[email_id]` | Destination email ID (DB record ID) | `12345` |
| `[email]` | Destination email address | `john@example.com` |
| `[first_name]` | Destination first name | `John` |
| `[last_name]` | Destination last name | `Doe` |
| `[return_path]` | Return path header value | `bounce@sender.com` |
| `[from_name]` | From display name | `Support Team` |
| `[subject]` | Email subject | `Your account update` |
| `[mail_date]` | Current date (YYYY-MM-DD) | `2025-01-15` |
| `[message_id]` | Generated message ID | `<uuid@domain.com>` |
| `[negative]` | Content from `4-negative.txt` | (news/junk text) |
| `[placeholder1]` ... `[placeholderN]` | Current placeholder value 1 to N | custom value |
| `[auto_reply_mailbox]` | Auto reply mailbox (if configured) | `noreply@sender.com` |

---

### 2. Unique Random Tags

These generate a **different** random value each time they are used (per-email randomization).

**Fixed size** (exact length):
```
[uan_12]   → 12-char unique alphanumeric random
[ua_8]     → 8-char unique alpha random
```

**Range size** (random length between min and max):
```
[uan_5_15]  → between 5 and 15 chars, alphanumeric
[ua_3_10]   → between 3 and 10 chars, alpha
```

| Tag Pattern | Description |
|-------------|-------------|
| `[ua_N]` or `[ua_N_M]` | Unique Alpha Random (letters only) |
| `[ual_N]` or `[ual_N_M]` | Unique Alpha Lowercase Random |
| `[uau_N]` or `[uau_N_M]` | Unique Alpha Uppercase Random |
| `[uan_N]` or `[uan_N_M]` | Unique Alphanumeric Random |
| `[uanl_N]` or `[uanl_N_M]` | Unique Alphanumeric Lowercase Random |
| `[uanu_N]` or `[uanu_N_M]` | Unique Alphanumeric Uppercase Random |
| `[un_N]` or `[un_N_M]` | Unique Numeric Random |
| `[uhu_N]` | Unique Uppercase Hex Random |
| `[uhl_N]` | Unique Lowercase Hex Random |

---

### 3. Random Tags (Fixed per Campaign Send)

These use `{...}` curly braces for **per-email** random (new value each email), and `[...]` square brackets for **fixed** (same value for entire campaign run).

#### Per-Email Random (curly braces `{type_N}`)

| Tag Pattern | Description |
|-------------|-------------|
| `{a_N}` | Alpha Random — new value per email |
| `{al_N}` | Alpha Lowercase Random |
| `{au_N}` | Alpha Uppercase Random |
| `{an_N}` | Alphanumeric Random |
| `{anl_N}` | Alphanumeric Lowercase Random |
| `{anu_N}` | Alphanumeric Uppercase Random |
| `{n_N}` | Numeric Random |

#### Fixed per Campaign Run (square brackets `[type_N]`)

| Tag Pattern | Description |
|-------------|-------------|
| `[a_N]` | Alpha Random — SAME value for all emails in campaign |
| `[al_N]` | Alpha Lowercase Random — fixed |
| `[au_N]` | Alpha Uppercase Random — fixed |
| `[an_N]` | Alphanumeric Random — fixed |
| `[anl_N]` | Alphanumeric Lowercase Random — fixed |
| `[anu_N]` | Alphanumeric Uppercase Random — fixed |
| `[n_N]` | Numeric Random — fixed |
| `[hu]` | Uppercase Hex Random |
| `[hl]` | Lowercase Hex Random |

**From `snd.py`**: The `fixed_random_values` dictionary stores fixed values. Once `[a_10]` is resolved, ALL future occurrences in the same campaign session use the same generated value.

---

### 4. Links Tags

| Tag | Description | Example |
|-----|-------------|---------|
| `[open]` | Open tracking pixel URL | `http://[domain]/[open]` |
| `[url]` | Click tracking URL | `http://[domain]/[url]` |
| `[unsub]` | Unsubscribe link | `http://[domain]/[unsub]` |
| `[optout]` | Opt-out link | `http://[domain]/[optout]` |
| `[LinksPlaceholder]` | Rotated link from `3-links.txt` | actual URL from file |

#### Short Links Tags (no domain tag needed, no `http://`)

| Tag | Description |
|-----|-------------|
| `[short_open]` | Short open tracking URL |
| `[short_url]` | Short click URL |
| `[short_unsub]` | Short unsubscribe URL |
| `[short_optout]` | Short opt-out URL |

---

### 5. Encryption Tags

Wrap content between begin and end tags to encrypt it:

| Tag Pattern | Encryption Type |
|-------------|----------------|
| `[enc_b64_b]` ... `[enc_b64_e]` | Encode text between in Base64 |
| `[enc_qp_b]` ... `[enc_qp_e]` | Encode in Quoted Printable |
| `[enc_hex_b]` ... `[enc_hex_e]` | Encode in Hex Unicode |

**Example**:
```
[enc_b64_b]Hello World[enc_b64_e]
→ SGVsbG8gV29ybGQ=
```

---

### 6. Boundary Tags

Used to generate consistent random boundaries in multipart emails:

```
[bond_N_[tag1]...[tagX]] & [bond_N]
```

- `N` = boundary index (1 to N)
- Content between bond tags gets replaced with `[bond_N]` + generated boundary string
- Ensures consistent MIME boundaries across multipart email sections

---

### 7. VMTA Types

Controls which Virtual MTA sends the email:

| VMTA Type | Description |
|-----------|-------------|
| **Default VMTA** | Sends with default virtual MTA. `[rdns]` = default RDNS, `[domain]` = default domain, `[custom_domain]` = empty |
| **Custom VMTA** | Sends with custom-created VMTA (if any). `[rdns]` = default, `[domain]` = custom domain, `[custom_domain]` = custom domain |
| **Merged VMTA** | Sends with custom VMTA (if any). `[rdns]` = default RDNS, `[domain]` = custom, `[custom_domain]` = custom |

---

## Header File Format (`0-header.txt`)

```
From: {n_3} <service_{n_15}@servicemaintlok.net>
Subject: [an_13]
List-ID: [an_15]]-1bf6-4bad-[n_4]-2c897fe51252
x-list-id: [an_15]]-1bf6-4bad-[n_4]-2c897fe51252
X-Custom-Header: custom_value
```

### How `snd.py` Parses It

```python
def process_header_file(file_path):
    headers = {}
    content = read_file(file_path)
    processed = replace_tags(content)  # All tags resolved first
    
    for line in processed.splitlines():
        if line.startswith('From:'):
            # Extract email from <...> and name before it
            headers['from_email'] = re.search(r'<([^>]+)>', line).group(1)
            headers['from_name'] = re.search(r'From:\s*([^<]+)', line).group(1).strip()
        elif line.startswith('Subject:'):
            headers['subject'] = re.search(r'Subject:\s*(.*)', line).group(1).strip()
        else:
            # All other headers stored as-is
            name, value = line.split(':', 1)
            headers[name.strip()] = value.strip()
    
    return headers
```

---

## Complete Tag Processing Order in `snd.py`

1. **Per-email random tags** `{type_N}` — replaced with new random each email
2. **`[mail_date]`** — replaced with `datetime.date.today().strftime('%Y-%m-%d')`
3. **Fixed random tags** `[type_N]` — replaced once, cached in `fixed_random_values` dict
4. **`[LinksPlaceholder]`** — rotated through lines in `3-links.txt` (round-robin)
5. **`[negative]`** — replaced with full content of `4-negative.txt`

---

## Usage Examples

### Subject line with randomization
```
[an_13] - Your account notification #{n_6}
→ "xK9mLpQrS4wT2 - Your account notification #847291"
```

### From header with random domain
```
From: Service{n_3} <info_{an_8}@{[al_12]}.net>
→ "From: Service847 <info_xK9mLpQr@abcdefghijkl.net>"
```

### HTML body with recipient data
```html
<p>Hello [first_name],</p>
<p>Your email [email] has been selected.</p>
<a href="[LinksPlaceholder]?sub=[uan_12]">Click here</a>
```

### Negative content injection (deliverability trick)
```html
<!-- Visible content -->
<div style="color:white;font-size:1px;">[negative]</div>
```

---

## Tags Specific to This System (Extended from snd.py)

These are ADDED by our system on top of the original snd.py tags:

| Tag | Description |
|-----|-------------|
| `{{offer.tracking_url}}` | Offer's click tracking URL from affiliate API |
| `{{offer.name}}` | Offer name |
| `{{offer.payout}}` | Offer payout amount |
| `{{offer.preview_url}}` | Landing page preview URL |
| `{{offer.subject}}` | Suggested subject from creative |
| `{{offer.from_name}}` | Suggested from name |
| `{{campaign.id}}` | Current campaign ID |
| `{{account.email}}` | Current sender account email |
| `{{account.group}}` | Current sender account group name |
| `{{list.name}}` | Recipient list name |
| `{{recipient.name}}` | Recipient name (parsed from list) |
| `{{recipient.email}}` | Recipient email |
