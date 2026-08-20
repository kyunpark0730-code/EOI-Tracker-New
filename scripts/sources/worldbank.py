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
MAX_PAGES = 100  # 최대 1만 건까지 - 정렬 순서와 무관하게 잘리는 문제 자체를 없애기 위함


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
        "order": "asc",
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
    total_seen = 0
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
                # GO=Goods(물품), CW=Civil Works(공사), CS=Consulting Services(컨설팅
                # 용역), NC=Non-Consulting Services 등을 구분하는 필드. 다산은 컨설팅
                # 용역만 참여하므로 fetch_all.py에서 이 필드로 물품 조달(GO)을 제외한다.
                "procurement_group": item.get("procurement_group", ""),
                "summary": _strip_html(item.get("notice_text", ""))[:500],
                # 분야 필터(is_relevant)용 원문 전체 텍스트. "summary"는 대시보드
                # 표시용으로 500자로 잘라두는데, 그 잘린 부분 뒤에 실제 과업범위
                # (예: "social safeguards management", "health service delivery
                # oversight" 등 제외 판단에 필요한 문구)가 나오는 경우가 있어서
                # (피지 PHIT 사업 사례) 필터는 항상 이 필드(전체 원문)를 봐야 한다.
                # fetch_all.py에서 필터링에 쓰고 최종 저장 전에 제거한다.
                # 분야 필터(is_relevant)용 원문 전체 텍스트. "summary"는 대시보드
                # 표시용으로 500자로 잘라두는데, 그 잘린 부분 뒤에 실제 과업범위
                # (예: "social safeguards management", "health service delivery
                # oversight" 등 제외 판단에 필요한 문구)가 나오는 경우가 있어서
                # (피지 PHIT 사업 사례) 필터는 이 필드(원문 앞부분 더 길게)를 봐야
                # 한다. 다만 원문 전체를 다 쓰면 공고 맨 끝에 항상 붙는 담당기관
                # 제출처 주소("Corner of Nationalist Road and Independence Avenue"
                # 같은 문구)에 있는 거리 이름이 "road" 등 INCLUDE 키워드에 우연히
                # 걸리는 문제가 있었다(잠비아 DZAP 사례). 과업범위/자격요건은
                # 보통 앞쪽 3000자 안에 다 나오고, 주소/연락처는 항상 맨 끝에
                # 붙으므로 3000자까지만 써서 이 오탐을 막는다.
                # fetch_all.py에서 필터링에 쓰고 최종 저장 전에 제거한다.
                "_filter_text": _strip_html(item.get("notice_text", ""))[:3000],
                "source": "World Bank",
                "source_url": f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{nid}",
            }

        total = int(data.get("total", 0))
        total_seen = total
        offset += ROWS_PER_PAGE
        if offset == ROWS_PER_PAGE:  # 첫 페이지에서 한 번만 출력
            print(f"[World Bank 디버그] 전체 열려있는 공고 수: {total}건 (최대 {ROWS_PER_PAGE * MAX_PAGES}건까지 수집)", file=sys.stderr)
        if offset >= total:
            break
        time.sleep(0.3)

    if total_seen > ROWS_PER_PAGE * MAX_PAGES:
        print(f"[World Bank 경고] 전체 {total_seen}건 중 {ROWS_PER_PAGE * MAX_PAGES}건만 수집됨 — 일부 공고가 잘렸을 수 있음", file=sys.stderr)

    return list(all_notices.values())
