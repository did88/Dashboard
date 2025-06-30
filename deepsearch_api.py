import os
import requests

BASE_URL = "https://api-v2.deepsearch.com/v2"

# 전역 캐시
SYMBOL_CACHE = None


def _headers():
    key = os.getenv("DEEPSEARCH_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEARCH_API_KEY is not set")
    return {
        "Content-Type": "application/json",
    }


def get_all_symbols() -> dict:
    """
    DeepSearch에서 전체 심볼 목록을 가져와
    종목명(name_kr) -> symbol_code 딕셔너리로 반환
    """
    api_key = os.getenv("DEEPSEARCH_API_KEY")
    url = f"{BASE_URL}/markets/symbols?api_key={api_key}"

    resp = requests.get(url, headers=_headers(), timeout=30)
    name_to_symbol = {}

    if resp.ok:
        data = resp.json()
        for item in data.get("items", []):
            kor_name = item.get("name_kr")
            symbol_code = item.get("symbol")
            if kor_name and symbol_code:
                name_to_symbol[kor_name] = symbol_code
        print(f"심볼 수집 완료. 총 {len(name_to_symbol)}건")
    else:
        print("심볼 목록 API 호출 실패:", resp.status_code, resp.text)

    return name_to_symbol


def find_symbol_by_name(name: str, name_to_symbol: dict) -> str:
    """
    종목명으로 심볼코드 찾기
    """
    return name_to_symbol.get(name)


def search_symbol(company_name: str) -> str:
    """
    기존 search_symbol()과 동일한 시그니처 유지.
    내부적으로 get_all_symbols()를 호출해 심볼 찾는다.
    호출 시 캐시 사용
    """
    global SYMBOL_CACHE

    if SYMBOL_CACHE is None:
        print("[INFO] SYMBOL_CACHE 비어있음 → 심볼 목록 불러오는 중...")
        SYMBOL_CACHE = get_all_symbols()
    else:
        print("[INFO] SYMBOL_CACHE 사용 중")

    symbol_code = find_symbol_by_name(company_name, SYMBOL_CACHE)

    if symbol_code:
        print(f"심볼 찾음: {company_name} -> {symbol_code}")
        return symbol_code
    else:
        print(f"심볼 찾지 못함: {company_name}")
        return None


def get_symbol_info(symbol_code: str) -> dict:
    """
    DeepSearch에서 단일 심볼 상세정보 조회
    """
    api_key = os.getenv("DEEPSEARCH_API_KEY")
    url = f"{BASE_URL}/markets/symbols/{symbol_code}?api_key={api_key}"

    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.ok:
        return resp.json()
    else:
        print("심볼 상세조회 실패:", resp.status_code, resp.text)
        return {}


def get_company_overview(symbol_id: str) -> dict:
    """
    DeepSearch에서 단일 심볼 상세정보(회사 개요) 조회
    """
    api_key = os.getenv("DEEPSEARCH_API_KEY")
    url = f"{BASE_URL}/markets/symbols/{symbol_id}?api_key={api_key}"

    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.ok:
        data = resp.json()
        overview = data.get("description_kr") or data.get("description")
        print("DeepSearch get_company_overview", symbol_id, bool(overview))
        return overview
    else:
        print("DeepSearch get_company_overview error", resp.status_code, resp.text)
        return {}


def get_latest_news(symbol_id: str, limit: int = 2) -> list:
    """
    DeepSearch에서 해당 종목의 최신 뉴스 조회
    """
    api_key = os.getenv("DEEPSEARCH_API_KEY")
    url = f"{BASE_URL}/news?api_key={api_key}"
    params = {"symbol": symbol_id, "size": limit}

    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    news_list = []
    if resp.ok:
        data = resp.json()
        for n in data.get("items", [])[:limit]:
            news_list.append({"title": n.get("title"), "link": n.get("link")})
        print("DeepSearch get_latest_news", symbol_id, len(news_list))
    else:
        print("DeepSearch get_latest_news error", resp.status_code, resp.text)
    return news_list


def parse_main_products(text: str, limit: int = 2) -> list:
    """
    기업 개요 텍스트에서 주요 제품 추출
    """
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
