# -*- coding: utf-8 -*-
"""
EIB(유럽투자은행) 조달공고(Procurement) 수집기.
브라우저 개발자도구로 확인한 내부 JSON API를 그대로 사용한다 (로그인 불필요, 공개 API).

※ 1차 버전: 필터링 없이 전체 목록을 가져온다 (사용자 요청에 따라 필터링은 추후 추가 예정).
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

API_BASE = "https://www.eib.org/provider-eib/app/list/medias/procurements"
LIST_PAGE_URL = "https://www.eib.org/en/about/procurement/all/index.htm"

ITEMS_PER_PAGE = 25
MAX_PAGES = 8  # 최대 200건 정도까지

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.eib.org/en/about/procurement/all/index.htm",
}


def _fetch_page(page_no: int) -> list:
    params = {
        "sortColumn": "configuration.contentStart",
        "sortDir": "desc",
        "pageNumber": str(page_no),
        "itemPerPage": str(ITEMS_PER_PAGE),
        "pageable": "true",
        "language": "EN",
        "defaultLanguage": "EN",
        "orYearTo": "true",
        "orYearFrom": "true",
        "procurementStatus": "All",
        "or_g_procurementInformations_type": "true",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)

    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            break
        except Exception as e:
            last_err = e
            print(f"[EIB 경고] page={page_no} 시도 {attempt + 1}/3 실패: {e}", file=sys.stderr)
            time.sleep(3)
    else:
        raise last_err

    data = json.loads(body)
    if isinstance(data, list):
        return data
    # 혹시 {"items": [...]} 형태로 올 경우 대비
    if isinstance(data, dict):
        return data.get("items", []) or data.get("data", [])
    return []


def _epoch_ms_to_dt(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def fetch() -> list:
    results = {}

    for page in range(MAX_PAGES):
        try:
            items = _fetch_page(page)
        except Exception as e:
            print(f"[EIB 경고] page={page} 요청 실패: {e}", file=sys.stderr)
            break

        if not items:
            break

        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            add_info = item.get("additionalInformation") or []
            status = add_info[0] if len(add_info) > 0 else ""
            category = add_info[1] if len(add_info) > 1 else ""
            reference = add_info[2] if len(add_info) > 2 else ""
            start_str = add_info[3] if len(add_info) > 3 else ""
            deadline_str = add_info[4] if len(add_info) > 4 else ""

            country = ""
            for tag in item.get("primaryTags") or []:
                if tag.get("subType") == "countries":
                    country = tag.get("label", "")
                    break

            sort_dt = _epoch_ms_to_dt(item.get("startDate")) or datetime.min

            uid = item.get("id") or item.get("url") or title
            results[uid] = {
                "_sort_date": sort_dt.isoformat(),
                "id": f"eib-{uid}",
                "notice_type": category or "Procurement",
                "notice_date": start_str,
                "submission_date": deadline_str,
                "country": country,
                "project_id": reference,
                "project_name": title,
                "bid_reference_no": reference,
                "bid_description": status,
                "procurement_method": "",
                "summary": "",
                "source": "EIB",
                "source_url": LIST_PAGE_URL,
            }

        if len(items) < ITEMS_PER_PAGE:
            break

    result = sorted(results.values(), key=lambda n: n.get("_sort_date") or "", reverse=True)
    for n in result:
        n.pop("_sort_date", None)
    return result
