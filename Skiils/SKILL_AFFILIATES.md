# SKILL: Affiliate Networks Integration

## Overview

Affiliate networks (called "Sponsors" in the UI) are the sources of offers and suppression lists. The system supports multiple API types. Each network has its own API credentials and configuration.

---

## Supported Affiliate Network APIs

### 1. Everflow API

**Docs**: https://docs.everflow.io/

```python
# services/affiliate_apis.py

class EverflowAPI:
    BASE_URL = "https://api.eflow.team/v1"
    
    def __init__(self, api_key: str, network_id: str = None):
        self.api_key = api_key
        self.network_id = network_id
        self.headers = {
            "X-Eflow-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def get_all_offers(self) -> list:
        """GET /v1/affiliates/offers"""
        response = requests.get(
            f"{self.BASE_URL}/affiliates/offers",
            headers=self.headers,
            params={"page": 1, "page_size": 500, "status": "active"}
        )
        return response.json().get("offers", [])
    
    def get_offer_by_id(self, offer_id: str) -> dict:
        """GET /v1/affiliates/offers/{offer_id}"""
        response = requests.get(
            f"{self.BASE_URL}/affiliates/offers/{offer_id}",
            headers=self.headers
        )
        return response.json()
    
    def get_offer_creatives(self, offer_id: str, max_creatives: int = 1) -> list:
        """GET /v1/affiliates/offers/{offer_id}/creatives"""
        response = requests.get(
            f"{self.BASE_URL}/affiliates/offers/{offer_id}/creatives",
            headers=self.headers,
            params={"page_size": max_creatives}
        )
        return response.json().get("creatives", [])
    
    def get_suppression_list(self, offer_id: str) -> list:
        """GET /v1/networks/offers/{offer_id}/suppression"""
        response = requests.get(
            f"{self.BASE_URL}/networks/offers/{offer_id}/suppression",
            headers=self.headers
        )
        return response.json().get("emails", [])
    
    def get_tracking_link(self, offer_id: str, sub1: str = None, sub2: str = None) -> str:
        """Build tracking URL with sub parameters"""
        offer = self.get_offer_by_id(offer_id)
        tracking_url = offer.get("tracking_url", "")
        if sub1:
            tracking_url += f"&sub1={sub1}"
        if sub2:
            tracking_url += f"&sub2={sub2}"
        return tracking_url
```

**Sub Parameters (from screenshot)**:
- Sub 1: `Mailer Id`, `Process Id`, `ISP Id`, `List Id`, `Email Id`, `Vmta Id`
- Sub 2: `Process Id`, `ISP Id`, `List Id`, `Email Id`, `Vmta Id`
- Sub 3: `List Id`, `Email Id`, `Vmta Id`, `Mailer Id`, `Process Id`, `ISP Id`

These map to tracking pixels and conversion tracking in Everflow.

---

### 2. Cake API

**Docs**: https://support.getcake.com/hc/en-us/categories/200709245

```python
class CakeAPI:
    def __init__(self, domain: str, api_key: str):
        self.domain = domain  # e.g. "yournetwork.go2jump.org"
        self.api_key = api_key
        self.base_url = f"https://{domain}/api/1"
    
    def get_all_offers(self) -> list:
        """POST /api/1/offers.asmx"""
        response = requests.post(
            f"{self.base_url}/offers.asmx/GetOffers",
            json={
                "api_key": self.api_key,
                "affiliate_id": 0,
                "vertical_id": 0,
                "offer_status_id": 1,  # active
                "start_at_row": 0,
                "row_limit": 500
            }
        )
        return response.json().get("offers", [])
    
    def get_offer_creatives(self, offer_id: int, creative_type: str = "email") -> list:
        response = requests.post(
            f"{self.base_url}/creative.asmx/GetCreatives",
            json={
                "api_key": self.api_key,
                "offer_id": offer_id,
                "creative_type": creative_type
            }
        )
        return response.json().get("creatives", [])
    
    def get_suppression(self, offer_id: int) -> list:
        response = requests.post(
            f"{self.base_url}/suppression.asmx/GetSuppressionList",
            json={
                "api_key": self.api_key,
                "offer_id": offer_id
            }
        )
        return response.json().get("emails", [])
```

---

### 3. HitPath API

```python
class HitPathAPI:
    def __init__(self, api_url: str, username: str, password: str, company_name: str):
        self.api_url = api_url
        self.username = username
        self.password = password
        self.company_name = company_name
    
    def authenticate(self) -> str:
        """Get session token"""
        response = requests.post(
            f"{self.api_url}/auth/login",
            json={
                "username": self.username,
                "password": self.password,
                "company": self.company_name
            }
        )
        return response.json().get("token")
    
    def get_offers(self) -> list:
        token = self.authenticate()
        response = requests.get(
            f"{self.api_url}/campaigns",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json().get("campaigns", [])
    
    def get_suppression(self, campaign_id: str) -> list:
        token = self.authenticate()
        response = requests.get(
            f"{self.api_url}/campaigns/{campaign_id}/suppression",
            headers={"Authorization": f"Bearer {token}"}
        )
        return response.json().get("emails", [])
```

---

## Add New Affiliate Network — UI Form Fields

Based on the screenshot (Image 1), here are all the fields and their meaning:

| UI Field | DB Column | Used By |
|----------|-----------|---------|
| Affiliate Id | `affiliate_id` | Display/reference |
| Affiliate Network Name | `name` | Display |
| Status | `status` | `activated` / `deactivated` |
| Affiliate Network Website | `website_url` | Reference |
| Username | `username` | HitPath, some custom APIs |
| Password | `password` | HitPath, some custom APIs |
| Api Platform | `api_platform` | `none`, `everflow`, `cake`, `hitpath`, `custom` |
| Network Id | `network_id` | Required for Cake and some platforms |
| Company Name | `company_name` | Required for HitPath only |
| Affiliate Network API Key | `api_key` | Everflow, some custom |
| API Username | `api_username` | Required for Geniads and similar |
| API Password | `api_password` | Required for Geniads and similar |

### Sub Parameter Checkboxes (Tracking)

Each network has 3 sub parameter slots (Sub 1, Sub 2, Sub 3). Each slot can include:
- `Mailer Id` — ID of the sending account
- `Process Id` — ID of the sending process/campaign run
- `ISP Id` — Target ISP identifier
- `List Id` — Recipient list ID
- `Email Id` — Unique email record ID
- `Vmta Id` — Virtual MTA identifier

These values are injected into the affiliate tracking URL when sending:
```
https://track.network.com/click?sub1={mailer_id}&sub2={list_id}&sub3={process_id}
```

---

## Add New Offer from Affiliate Network — UI Form Fields

Based on screenshot (Image 2):

| UI Field | Behavior |
|----------|---------|
| Affiliate Network | Dropdown — select which network to pull from |
| Get All Offers | Checkbox — if checked, fetches ALL offers via API |
| Offers Production IDs | If not "Get All", paste specific offer IDs (one per line) |
| Max Number Of Creatives | How many email creatives to import per offer (default: 1) |
| Get All Creatives | Override max and get everything |

### "API" Button (top right)

Toggles between:
- **API mode**: Pull offer data from the affiliate network API
- **Manual mode**: Enter offer data manually (name, URL, etc.)

---

## Affiliate Network Service Factory

```python
# services/affiliate_apis.py

def get_affiliate_client(network: AffiliateNetwork):
    """Factory: return correct API client based on network config"""
    
    platform = network.api_platform
    
    if platform == "everflow":
        return EverflowAPI(
            api_key=network.api_key,
            network_id=network.network_id
        )
    
    elif platform == "cake":
        return CakeAPI(
            domain=network.website_url,
            api_key=network.api_key
        )
    
    elif platform == "hitpath":
        return HitPathAPI(
            api_url=network.website_url,
            username=network.api_username,
            password=network.api_password,
            company_name=network.company_name
        )
    
    elif platform == "custom":
        return CustomAPI(
            base_url=network.website_url,
            api_key=network.api_key,
            username=network.username,
            password=network.password
        )
    
    else:  # none / manual
        return None


async def import_offers_from_network(network_id: int, offer_ids: list = None,
                                      get_all: bool = False, max_creatives: int = 1):
    """
    Pull offers from affiliate API and store in DB.
    Called when user clicks 'Get Offers' in Add New Offer form.
    """
    network = await db.get(AffiliateNetwork, network_id)
    client = get_affiliate_client(network)
    
    if client is None:
        raise ValueError("Network has no API platform configured")
    
    if get_all:
        raw_offers = client.get_all_offers()
    else:
        raw_offers = [client.get_offer_by_id(oid) for oid in offer_ids]
    
    saved = []
    for raw in raw_offers:
        # Normalize across platforms
        offer = normalize_offer(raw, network.api_platform)
        
        # Get creatives (email HTML bodies)
        creatives = client.get_offer_creatives(offer["id"], max_creatives)
        
        # Get suppression list
        suppression = client.get_suppression(offer["id"])
        
        # Save to DB
        db_offer = await save_offer(offer, network_id, creatives, suppression)
        saved.append(db_offer)
    
    return saved
```

---

## Offer Data Structure (in DB)

```python
class Offer(Base):
    __tablename__ = "offers"
    
    id = Column(Integer, primary_key=True)
    network_id = Column(Integer, ForeignKey("affiliate_networks.id"))
    
    # From API
    external_id = Column(String)          # ID in the affiliate network
    name = Column(String)                 # Offer name
    description = Column(Text)
    tracking_url = Column(String)         # Click tracking URL
    preview_url = Column(String)          # Preview/landing page
    payout = Column(Float)                # $ per conversion
    currency = Column(String, default="USD")
    
    # Email creatives from API
    subject_line = Column(String)         # Pre-written subject
    from_name = Column(String)            # Suggested from name
    html_body = Column(Text)              # HTML email creative
    
    # Config
    is_active = Column(Boolean, default=True)
    max_sends_per_day = Column(Integer)
    
    # Relationships
    suppression_list = relationship("SuppressionEntry", back_populates="offer")
    data_fields = relationship("OfferDataField", back_populates="offer")
```

---

## Suppression List Auto-Import

When an offer is imported from an affiliate API:

1. System calls `client.get_suppression(offer_id)`
2. Returns list of emails to NEVER send to for this offer
3. Stored in `suppression_list` table linked to `offer_id`
4. **Before every send**: filter recipients against this list automatically

```python
async def filter_recipients(recipients: list, offer_id: int) -> list:
    """Remove suppressed and blacklisted emails before sending"""
    
    # Get suppression list for this offer
    suppressed = await db.query(SuppressionEntry).filter(
        SuppressionEntry.offer_id == offer_id
    ).all()
    suppressed_emails = {s.email.lower() for s in suppressed}
    
    # Get global blacklist
    blacklisted = await db.query(Blacklist).all()
    blacklisted_emails = {b.email.lower() for b in blacklisted}
    blacklisted_domains = {b.domain.lower() for b in blacklisted if b.domain}
    
    clean = []
    filtered_count = 0
    for recipient in recipients:
        email = recipient.lower()
        domain = email.split("@")[1] if "@" in email else ""
        
        if email in suppressed_emails:
            filtered_count += 1
            continue
        if email in blacklisted_emails:
            filtered_count += 1
            continue
        if domain in blacklisted_domains:
            filtered_count += 1
            continue
        
        clean.append(recipient)
    
    return clean, filtered_count
```
