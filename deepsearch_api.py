import os
import requests
from typing import List, Optional

DEEPSEARCH_API_KEY = os.getenv("DEEPSEARCH_API_KEY")
BASE_URL = "https://api.deepsearch.com/v1"


def _headers():
    if not DEEPSEARCH_API_KEY:
        raise RuntimeError("DEEPSEARCH_API_KEY is not set")
    return {"Authorization": f"Bearer {DEEPSEARCH_API_KEY}"}


def search_symbol(company_name: str) -> Optional[str]:
    """Return symbol_id for given company name."""
    url = f"{BASE_URL}/symbol"  # hypothetical endpoint
    params = {"query": company_name}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    if resp.ok:
        data = resp.json()
        items = data.get("items")
        if items:
            return items[0].get("symbol_id")
    return None


def get_company_overview(symbol_id: str) -> Optional[str]:
    """Fetch overview/description text for the symbol."""
    url = f"{BASE_URL}/symbol/{symbol_id}/info"
    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.ok:
        data = resp.json()
        return data.get("overview")
    return None


def get_latest_news(symbol_id: str, limit: int = 2) -> List[dict]:
    """Return latest news items with title and url."""
    url = f"{BASE_URL}/news"
    params = {"symbol_id": symbol_id, "size": limit}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    result = []
    if resp.ok:
        data = resp.json()
        for n in data.get("items", [])[:limit]:
            result.append({"title": n.get("title"), "link": n.get("link")})
    return result


def parse_main_products(text: str, limit: int = 2) -> List[str]:
    """Extract major products from overview text."""
    if not text:
        return []
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(keyword in line for keyword in ["주요", "제품", "서비스"]):
            candidates.append(line)
    if not candidates:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        candidates.extend(sentences)
    return candidates[:limit]
