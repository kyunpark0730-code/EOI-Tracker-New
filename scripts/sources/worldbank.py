# -*- coding: utf-8 -*-
"""
World Bank 공식 조달 공고(Procurement Notices) API 수집기.
마감일(제출기한)이 지나지 않은 공고만 가져온다.
"""

import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

API_BASE = "https://search.worldbank.org/api/v2/procnotices"

NOTICE_TYPES = [
    "Invitation for Bids",
    "Invitation for Prequalification",
    "Request for Expression of Interest",
    "General Procurement Notice",
    "Specific Procurement Notice",
    "Request for Proposals",
]

ROWS_PER_PAGE = 100
MAX_PAGES = 20


def _parse_date(raw: str):
    if not raw:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_page(offset: int, deadline_strdate: str) -> dict:
    import json
    notice_type_value = "^".join(NOTICE_TYPES)
    params = {
        "format": "json",
        "rows": str(ROWS_PER_PAGE),
        "os": str(offset),
        "srt": "submission_deadline_date",
        "order": "desc",
        "apilang": "en",
        "srce": "both",
        "notice_type_exact": notice_type_value,
        "deadline_strdate": deadline_strdate,
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params, safe='^')}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _extract_items(data: dict):
    raw = data.get("procnotices", [])
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return raw
    return []


def fetch() -> list:
    """공통 스키마의 공고 딕셔너리 리스트를 반환한다."""
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    deadline_strdate = today.strftime("%Y-%m-%d")
    all_notices = {}

    offset = 0
    for _ in range(MAX_PAGES):
        try:
            data = _fetch_page(offset, deadline_strdate)
        except Exception as e:
            print(f"[World Bank 경고] offset={offset} 요청 실패: {e}", file=sys.stderr)
            break

        items = _extract_items(data)
        if not items:
            break

        for item in items:
            nid = item.get("id")
            if not nid:
                continue

            deadline_raw = item.get("submission_deadline_date") or item.get("submission_date", "")
            deadline_parsed = _parse_date(deadline_raw)
            notice_date_raw = item.get("noticedate", "")
            notice_date_parsed = _parse_date(notice_date_raw)

            sort_dt = deadline_parsed or notice_date_parsed
            if sort_dt is None:
                continue

            all_notices[f"wb-{nid}"] = {
                "_sort_date": sort_dt.isoformat(),
                "id": f"wb-{nid}",
                "notice_type": item.get("notice_type", ""),
                "notice_date": notice_date_raw,
                "submission_date": deadline_raw,
                "country": item.get("project_ctry_name", ""),
                "project_id": item.get("project_id", ""),
                "project_name": item.get("project_name", ""),
                "bid_reference_no": item.get("bid_reference_no", ""),
                "bid_description": item.get("bid_description", ""),
                "procurement_method": item.get("procurement_method_name", ""),
                "summary": _strip_html(item.get("notice_text", ""))[:500],
                "source": "World Bank",
                "source_url": f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}",
            }

        total = int(data.get("total", 0))
        offset += ROWS_PER_PAGE
        if offset >= total:
            break
        time.sleep(0.3)

    return list(all_notices.values())
