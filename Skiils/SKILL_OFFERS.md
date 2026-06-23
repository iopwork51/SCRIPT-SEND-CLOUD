# SKILL: Offers Management

## Overview

Offers come from affiliate networks (Everflow, Cake, HitPath). Each offer has a tracking URL, creatives (HTML email bodies), and a suppression list. The system imports these via API and allows manual CRUD on the data fields.

---

## Offer Lifecycle

```
Affiliate Network (API)
        ↓
  [Import Offers]
        ↓
  Offers Table (DB)
        ↓
  ├── Data Fields (CRUD)      ← landing URL, discount code, product name, etc.
  ├── Suppression List        ← auto-imported from network API
  └── HTML Creatives          ← email body template from network
        ↓
  Campaign uses Offer
        ↓
  Tags {{offer.X}} replaced in email body/subject
```

---

## Add New Offer — UI Flow (from Screenshot 2)

### Step 1: Select Affiliate Network
Dropdown shows all networks with status "activated".

### Step 2: Choose Import Mode

**API Mode** (toggle = "API"):
- "Get All Offers" checkbox → if checked, fetch everything from network API
- OR paste specific offer Production IDs (one per line)
- "Max Number of Creatives" → how many HTML creatives to import per offer (default: 1)
- "Get All Creatives" → override max, import all creatives

**Manual Mode** (toggle = other):
- Enter offer details manually (name, tracking URL, description, payout)
- No API call made

### Step 3: Click "Get Offers"
- System calls affiliate network API
- Shows list of available offers
- User selects which to save
- System auto-imports suppression list for each selected offer

---

## Offer Data Fields CRUD

Each offer can have custom key-value data fields that get injected into email templates via `{{offer.data.FIELD_KEY}}`.

### Common Data Fields by Offer Type

**Dating Offer**:
```
landing_url    = https://dating-site.com/lp?ref=XXXX
discount_code  = SAVE20
product_name   = Premium Dating
headline       = Find Your Match Today
cta_text       = Join Free
```

**Finance Offer**:
```
landing_url    = https://finance-app.com/apply
offer_amount   = $500
apr_rate       = 5.99%
headline       = Get Approved in Minutes
logo_url       = https://cdn.site.com/logo.png
```

**E-commerce Offer**:
```
landing_url    = https://shop.com/deal
product_name   = Wireless Earbuds Pro
original_price = $99.99
sale_price     = $49.99
discount_pct   = 50
image_url      = https://cdn.shop.com/product.jpg
```

### Data Fields in Email Template

```html
<!-- In HTML body template -->
<h1>{{offer.data.headline}}</h1>
<p>Get {{offer.data.product_name}} for only {{offer.data.sale_price}}</p>
<a href="{{offer.tracking_url}}">{{offer.data.cta_text}}</a>

<!-- Also available directly -->
<a href="{{offer.tracking_url}}">Click Here</a>
<p>Offer pays: {{offer.payout}} per conversion</p>
```

---

## Sub Parameters (Tracking)

Each affiliate network has Sub 1 / Sub 2 / Sub 3 configured with checkboxes.
These are injected into the tracking URL automatically during send.

### Available Sub Values

| Value | Description | Use Case |
|-------|-------------|---------|
| `Mailer Id` | ID of the sender account | Track which account drove conversions |
| `Process Id` | Campaign run ID | Track which campaign batch |
| `ISP Id` | Target ISP code | Track which email provider |
| `List Id` | Recipient list ID | Track which list performed best |
| `Email Id` | Recipient record ID | Individual email tracking |
| `Vmta Id` | Virtual MTA identifier | For dedicated SMTP servers |

### How It Works in Code

```python
def build_tracking_url(offer: Offer, network: AffiliateNetwork,
                        context: dict) -> str:
    """
    Build the full tracking URL with sub parameters.
    context = {
        "mailer_id": account.id,
        "process_id": campaign.id,
        "list_id": recipient_list.id,
        "email_id": recipient.id,
        "isp_id": get_isp_code(recipient.email),
        "vmta_id": None  # if applicable
    }
    """
    base_url = offer.tracking_url
    sub_config = network.sub_config  # e.g. {"sub1": ["mailer_id"], "sub2": ["list_id", "process_id"]}
    
    params = {}
    for sub_key, value_keys in sub_config.items():
        # Build sub value from multiple fields joined by underscore
        sub_value = "_".join(str(context.get(k, "")) for k in value_keys if context.get(k))
        if sub_value:
            params[sub_key] = sub_value
    
    if params:
        from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
        parsed = urlparse(base_url)
        existing = parse_qs(parsed.query)
        existing.update({k: [v] for k, v in params.items()})
        new_query = urlencode({k: v[0] for k, v in existing.items()})
        base_url = urlunparse(parsed._replace(query=new_query))
    
    return base_url
```

---

## Suppression List Management

### Auto-Import on Offer Creation

```python
async def import_offer_with_suppression(network_id: int, offer_id: str, db):
    network = await db.get(AffiliateNetwork, network_id)
    client = get_affiliate_client(network)
    
    # Get offer details
    raw_offer = client.get_offer_by_id(offer_id)
    
    # Get suppression list from affiliate API
    suppression_emails = client.get_suppression(offer_id)
    
    # Save offer to DB
    offer = Offer(
        network_id=network_id,
        external_id=raw_offer["id"],
        name=raw_offer["name"],
        tracking_url=raw_offer["tracking_url"],
        payout=raw_offer.get("payout", 0),
        # ... etc
    )
    db.add(offer)
    await db.flush()  # Get offer.id
    
    # Bulk insert suppression list
    suppression_records = [
        SuppressionEntry(email=email.lower().strip(), offer_id=offer.id)
        for email in suppression_emails
        if email and "@" in email
    ]
    db.add_all(suppression_records)
    await db.commit()
    
    return offer, len(suppression_records)
```

### Manual Suppression Import

```
POST /api/suppression/import
Body: {
    "offer_id": 123,
    "emails": ["user1@example.com", "user2@example.com"],
    "source": "manual"  // or "api_sync"
}
```

### Re-sync Suppression from API

```python
# Called from UI button "Sync Suppression" on offer detail page
async def sync_suppression(offer_id: int, db):
    offer = await db.get(Offer, offer_id)
    network = await db.get(AffiliateNetwork, offer.network_id)
    client = get_affiliate_client(network)
    
    # Delete old suppression for this offer
    await db.execute(
        delete(SuppressionEntry).where(SuppressionEntry.offer_id == offer_id)
    )
    
    # Re-import fresh suppression
    fresh = client.get_suppression(offer.external_id)
    db.add_all([
        SuppressionEntry(email=e.lower().strip(), offer_id=offer_id)
        for e in fresh if e and "@" in e
    ])
    await db.commit()
    return len(fresh)
```

---

## Normalizing Offers Across Platforms

```python
def normalize_offer(raw: dict, platform: str) -> dict:
    """Convert platform-specific offer format to our standard format"""
    
    if platform == "everflow":
        return {
            "external_id": str(raw.get("network_offer_id", raw.get("id"))),
            "name": raw.get("name", ""),
            "description": raw.get("description", ""),
            "tracking_url": raw.get("tracking_url", ""),
            "preview_url": raw.get("preview_url", ""),
            "payout": float(raw.get("default_payout", 0)),
            "currency": raw.get("currency", "USD"),
            "suggested_subject": raw.get("email_subject", ""),
            "suggested_from_name": raw.get("from_name", ""),
        }
    
    elif platform == "cake":
        return {
            "external_id": str(raw.get("offer_id", "")),
            "name": raw.get("offer_name", ""),
            "description": raw.get("offer_description", ""),
            "tracking_url": raw.get("offer_url", ""),
            "preview_url": raw.get("preview_url", ""),
            "payout": float(raw.get("payout_amount", 0)),
            "currency": "USD",
            "suggested_subject": "",
            "suggested_from_name": "",
        }
    
    elif platform == "hitpath":
        return {
            "external_id": str(raw.get("campaign_id", "")),
            "name": raw.get("campaign_name", ""),
            "description": raw.get("description", ""),
            "tracking_url": raw.get("click_url", ""),
            "preview_url": raw.get("preview_url", ""),
            "payout": float(raw.get("payout", 0)),
            "currency": raw.get("currency", "USD"),
            "suggested_subject": raw.get("email_subject", ""),
            "suggested_from_name": raw.get("from_name", ""),
        }
    
    else:  # manual / custom
        return raw  # already in our format
```
