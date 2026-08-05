# -*- coding: utf-8 -*-
"""
해외건설협회(ICAK) 입찰공고 게시판 수집기.
브라우저 개발자도구로 확인한 내부 JSON API를 그대로 사용한다 (로그인 불필요, 공개 API).
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

API_URL = (
    "https://www.icak.or.kr/board/api/bbsList"
    "?pageIndex=1&bbsId=705&expnsItmList%5B0%5D.cnTxt=&limit=100&searchInputOpt="
)
DETAIL_BASE = "https://www.icak.or.kr/board/bidPblancView"

LOOKBACK_DAYS = 30


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_dt(raw: str):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch() -> list:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    results = []

    try:
        data = _fetch_json(API_URL)
    except Exception as e:
        print(f"[ICAK 경고] 요청 실패: {e}", file=sys.stderr)
        return []

    items = data.get("data", [])
    if isinstance(items, dict):
        items = [items]

    for item in items:
        sn = item.get("sn")
        if sn is None:
            continue

        posted_raw = item.get("pstgBgngDt", "")
        posted_dt = _parse_dt(posted_raw)

        # 최근 N일 이내에 게시된 것만 (마감일이 먼 미래(상시공고)인 경우도 있어
        # 게시일 기준으로 최신 여부를 판단)
        if posted_dt and posted_dt < cutoff:
            continue

        deadline_raw = item.get("pstgEndDt", "")

        results.append({
            "id": f"icak-{sn}",
            "notice_type": item.get("cateNm") or "입찰공고",
            "notice_date": posted_raw,
            "submission_date": deadline_raw,
            "country": "대한민국",
            "project_id": "",
            "project_name": item.get("titl", ""),
            "bid_reference_no": "",
            "bid_description": "",
            "procurement_method": "",
            "summary": _strip_html(item.get("cnTxt", ""))[:500],
            "source": "해외건설협회(ICAK)",
            "source_url": "https://www.icak.or.kr/board/bidPblancList",
        })

    return results
