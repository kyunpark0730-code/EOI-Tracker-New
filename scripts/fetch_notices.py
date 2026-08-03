#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
World Bank 공식 조달 공고(Procurement Notices) API를 호출해서
현재 마감되지 않은(제출기한이 지나지 않은) EOI / 입찰 공고를 수집하고
data/notices.json 으로 저장한다.

World Bank 공식 사이트(worldbank.org/ext/en/what-we-do/project-procurement/for-suppliers)가
실제로 사용하는 API 방식을 그대로 따른다:
  - 엔드포인트: https://search.worldbank.org/api/v2/procnotices
  - 정렬: submission_deadline_date desc (마감일 기준, 게시일 기준 아님)
  - 필터: deadline_strdate = 오늘 날짜  → 마감일이 오늘 이후인, 즉 "아직 지원 가능한" 공고만
  - notice_type_exact 값은 '^'로 구분해서 한 번에 여러 유형 조회 가능
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

API_BASE = "https://search.worldbank.org/api/v2/procnotices"

# 취합 대상 공고 유형 ('^'로 묶어서 한 번에 조회)
NOTICE_TYPES = [
    "Invitation for Bids",
    "Invitation for Prequalification",
    "Request for Expression of Interest",
    "General Procurement Notice",
    "Specific Procurement Notice",
    "Request for Proposals",
]

ROWS_PER_PAGE = 100
MAX_PAGES = 20  # 넉넉하게 (마감 안 된 공고만 나오므로 전체 건수가 21일 lookback 때보다 훨씬 적음)


def parse_date(raw: str):
    """'31-Oct-2019' 또는 'YYYY-MM-DD' 형식 문자열을 datetime으로 변환."""
    if not raw:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_page(offset: int, deadline_strdate: str) -> dict:
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


def strip_html(text: str) -> str:
    import re
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_items(data: dict):
    """v2 API는 procnotices가 리스트일 수도, id를 key로 하는 dict일 수도 있어 둘 다 처리."""
    raw = data.get("procnotices", [])
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return raw
    return []


def collect() -> list:
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    deadline_strdate = today.strftime("%Y-%m-%d")
    all_notices = {}

    offset = 0
    for page in range(MAX_PAGES):
        try:
            data = fetch_page(offset, deadline_strdate)
        except Exception as e:
            print(f"[경고] offset={offset} 요청 실패: {e}", file=sys.stderr)
            break

        items = extract_items(data)
        if not items:
            break

        for item in items:
            nid = item.get("id")
            if not nid:
                continue

            deadline_raw = item.get("submission_deadline_date") or item.get("submission_date", "")
            deadline_parsed = parse_date(deadline_raw)
            notice_date_raw = item.get("noticedate", "")
            notice_date_parsed = parse_date(notice_date_raw)

            # 정렬 기준 날짜: 마감일 우선, 없으면 게시일
            sort_dt = deadline_parsed or notice_date_parsed
            if sort_dt is None:
                continue  # 날짜를 전혀 알 수 없는 항목은 제외 (fail-safe)

            all_notices[nid] = {
                "_sort_date": sort_dt.isoformat(),
                "id": nid,
                "notice_type": item.get("notice_type", ""),
                "notice_date": notice_date_raw,
                "submission_date": deadline_raw,
                "country": item.get("project_ctry_name", ""),
                "project_id": item.get("project_id", ""),
                "project_name": item.get("project_name", ""),
                "bid_reference_no": item.get("bid_reference_no", ""),
                "bid_description": item.get("bid_description", ""),
                "procurement_method": item.get("procurement_method_name", ""),
                "contact_name": item.get("contact_name", ""),
                "contact_organization": item.get("contact_organization", ""),
                "contact_email": item.get("contact_email", ""),
                "summary": strip_html(item.get("notice_text", ""))[:500],
                "source": "World Bank",
                "source_url": f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}",
            }

        total = int(data.get("total", 0))
        offset += ROWS_PER_PAGE
        if offset >= total:
            break
        time.sleep(0.3)

    def sort_key(n):
        return n.get("_sort_date") or ""

    result = sorted(all_notices.values(), key=sort_key, reverse=True)
    for n in result:
        n.pop("_sort_date", None)
    return result


def main():
    notices = collect()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filter": "마감일(제출기한)이 지나지 않은 공고만 (deadline_strdate = 오늘)",
        "count": len(notices),
        "notices": notices,
    }
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "notices.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"수집 완료: {len(notices)}건 -> {out_path}")


if __name__ == "__main__":
    main()
