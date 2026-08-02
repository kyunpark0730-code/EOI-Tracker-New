#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
World Bank 공식 조달 공고(Procurement Notices) API를 호출해서
최근 EOI / 입찰 관련 공고를 수집하고 data/notices.json 으로 저장한다.

API 문서: http://search.worldbank.org/api/procnotices
- notice_type 값 예시:
  "Request for Expression of Interest" (EOI)
  "Invitation for Bids"
  "General Procurement Notice"
  "Specific Procurement Notice"
  "Request for Proposals"
- 로그인/인증 불필요, robots.txt 차단 없음 (공식 공개 API)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

API_BASE = "http://search.worldbank.org/api/procnotices"

# 취합 대상 공고 유형 (필요하면 여기 리스트를 조정)
NOTICE_TYPES = [
    "Request for Expression of Interest",
    "Invitation for Bids",
    "General Procurement Notice",
    "Specific Procurement Notice",
    "Request for Proposals",
]

# 최근 N일 이내 공고만 수집 (기본 21일 - 매일 갱신되므로 여유있게)
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "21"))

# 한 번에 가져올 최대 건수 (페이지당 100, 넉넉히 여러 페이지)
ROWS_PER_PAGE = 100
MAX_PAGES = 10


def fetch_page(notice_type: str, offset: int, start_date: str) -> dict:
    params = {
        "format": "json",
        "rows": str(ROWS_PER_PAGE),
        "os": str(offset),
        "strdate": start_date,
        "notice_type_exact": notice_type,
        "srt": "noticedate",
        "order": "desc",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def strip_html(text: str) -> str:
    """아주 단순한 HTML 태그 제거 (미리보기용)."""
    import re
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collect() -> list:
    start_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    all_notices = {}

    for notice_type in NOTICE_TYPES:
        offset = 0
        for page in range(MAX_PAGES):
            try:
                data = fetch_page(notice_type, offset, start_date)
            except Exception as e:
                print(f"[경고] {notice_type} offset={offset} 요청 실패: {e}", file=sys.stderr)
                break

            items = data.get("procnotices", [])
            if not items:
                break

            for item in items:
                nid = item.get("id")
                if not nid:
                    continue
                all_notices[nid] = {
                    "id": nid,
                    "notice_type": item.get("notice_type", ""),
                    "notice_date": item.get("noticedate", ""),
                    "submission_date": item.get("submission_date", ""),
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
            time.sleep(0.3)  # 서버 부담 방지

    # 최신순 정렬 (notice_date 문자열 기준, 형식이 제각각일 수 있어 안전하게 처리)
    def sort_key(n):
        return n.get("notice_date") or n.get("submission_date") or ""

    result = sorted(all_notices.values(), key=sort_key, reverse=True)
    return result


def main():
    notices = collect()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": LOOKBACK_DAYS,
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
