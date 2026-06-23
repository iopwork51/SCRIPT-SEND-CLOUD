import requests
from typing import Optional


class EverflowAPI:
    BASE_URL = "https://api.eflow.team/v1"

    def __init__(self, api_key: str, network_id: str = None):
        self.api_key = api_key
        self.network_id = network_id
        self.headers = {"X-Eflow-API-Key": api_key, "Content-Type": "application/json"}

    def get_all_offers(self) -> list:
        r = requests.get(
            f"{self.BASE_URL}/affiliates/offers",
            headers=self.headers,
            params={"page": 1, "page_size": 500, "status": "active"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("offers", [])

    def get_offer_by_id(self, offer_id: str) -> dict:
        r = requests.get(f"{self.BASE_URL}/affiliates/offers/{offer_id}", headers=self.headers, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_offer_creatives(self, offer_id: str, max_creatives: int = 1) -> list:
        r = requests.get(
            f"{self.BASE_URL}/affiliates/offers/{offer_id}/creatives",
            headers=self.headers,
            params={"page_size": max_creatives},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("creatives", [])

    def get_suppression(self, offer_id: str) -> list:
        r = requests.get(
            f"{self.BASE_URL}/networks/offers/{offer_id}/suppression",
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("emails", [])


class CakeAPI:
    def __init__(self, domain: str, api_key: str):
        self.domain = domain
        self.api_key = api_key
        self.base_url = f"https://{domain}/api/1"

    def get_all_offers(self) -> list:
        r = requests.post(
            f"{self.base_url}/offers.asmx/GetOffers",
            json={"api_key": self.api_key, "affiliate_id": 0, "vertical_id": 0,
                  "offer_status_id": 1, "start_at_row": 0, "row_limit": 500},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("offers", [])

    def get_offer_by_id(self, offer_id: str) -> dict:
        r = requests.post(
            f"{self.base_url}/offers.asmx/GetOffers",
            json={"api_key": self.api_key, "offer_id": int(offer_id)},
            timeout=15,
        )
        r.raise_for_status()
        offers = r.json().get("offers", [])
        return offers[0] if offers else {}

    def get_offer_creatives(self, offer_id: str, max_creatives: int = 1) -> list:
        r = requests.post(
            f"{self.base_url}/creative.asmx/GetCreatives",
            json={"api_key": self.api_key, "offer_id": int(offer_id), "creative_type": "email"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("creatives", [])[:max_creatives]

    def get_suppression(self, offer_id: str) -> list:
        r = requests.post(
            f"{self.base_url}/suppression.asmx/GetSuppressionList",
            json={"api_key": self.api_key, "offer_id": int(offer_id)},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("emails", [])


class HitPathAPI:
    def __init__(self, api_url: str, username: str, password: str, company_name: str):
        self.api_url = api_url
        self.username = username
        self.password = password
        self.company_name = company_name
        self._token: Optional[str] = None

    def authenticate(self) -> str:
        r = requests.post(
            f"{self.api_url}/auth/login",
            json={"username": self.username, "password": self.password, "company": self.company_name},
            timeout=15,
        )
        r.raise_for_status()
        self._token = r.json().get("token")
        return self._token

    def _headers(self) -> dict:
        if not self._token:
            self.authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    def get_all_offers(self) -> list:
        r = requests.get(f"{self.api_url}/campaigns", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("campaigns", [])

    def get_offer_by_id(self, offer_id: str) -> dict:
        r = requests.get(f"{self.api_url}/campaigns/{offer_id}", headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json()

    def get_offer_creatives(self, offer_id: str, max_creatives: int = 1) -> list:
        r = requests.get(f"{self.api_url}/campaigns/{offer_id}/creatives", headers=self._headers(), timeout=15)
        r.raise_for_status()
        return r.json().get("creatives", [])[:max_creatives]

    def get_suppression(self, offer_id: str) -> list:
        r = requests.get(f"{self.api_url}/campaigns/{offer_id}/suppression", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("emails", [])


def get_affiliate_client(network):
    platform = network.api_platform
    if platform == "everflow":
        return EverflowAPI(api_key=network.api_key, network_id=network.network_id)
    elif platform == "cake":
        domain = network.website_url.replace("https://", "").replace("http://", "").rstrip("/")
        return CakeAPI(domain=domain, api_key=network.api_key)
    elif platform == "hitpath":
        return HitPathAPI(
            api_url=network.website_url,
            username=network.api_username or network.username,
            password=network.api_password or network.password,
            company_name=network.company_name or "",
        )
    return None


def normalize_offer(raw: dict, platform: str) -> dict:
    if platform == "everflow":
        return {
            "external_id": str(raw.get("network_offer_id", raw.get("id", ""))),
            "name": raw.get("name", ""),
            "description": raw.get("description", ""),
            "tracking_url": raw.get("tracking_url", ""),
            "preview_url": raw.get("preview_url", ""),
            "payout": float(raw.get("default_payout", 0) or 0),
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
            "payout": float(raw.get("payout_amount", 0) or 0),
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
            "payout": float(raw.get("payout", 0) or 0),
            "currency": raw.get("currency", "USD"),
            "suggested_subject": raw.get("email_subject", ""),
            "suggested_from_name": raw.get("from_name", ""),
        }
    return raw


def build_tracking_url(tracking_url: str, sub_config: dict, context: dict) -> str:
    """Inject sub parameters into tracking URL based on network sub_config."""
    from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

    if not sub_config or not tracking_url:
        return tracking_url

    params = {}
    for sub_key, value_keys in sub_config.items():
        if isinstance(value_keys, list):
            sub_value = "_".join(str(context.get(k, "")) for k in value_keys if context.get(k))
        else:
            sub_value = str(context.get(value_keys, ""))
        if sub_value:
            params[sub_key] = sub_value

    if params:
        parsed = urlparse(tracking_url)
        existing = parse_qs(parsed.query)
        existing.update({k: [v] for k, v in params.items()})
        new_query = urlencode({k: v[0] for k, v in existing.items()})
        tracking_url = urlunparse(parsed._replace(query=new_query))

    return tracking_url
