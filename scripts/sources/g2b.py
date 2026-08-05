# -*- coding: utf-8 -*-
"""
조달청 나라장터 "입찰공고정보서비스" 공식 API 수집기.
공공데이터포털(data.go.kr)에서 발급받은 인증키가 필요하며,
환경변수 G2B_API_KEY 로 전달받는다 (GitHub Actions Secrets에서 주입).

조건 (사용자가 나라장터 사이트에서 직접 검색했던 조건과 동일하게 맞춤):
- 용역 분야 입찰공고
- 수요기관명에 "해외"가 포함된 공고만 (예: 한국해외인프라도시개발지원공사 등)
- 최근 6개월 이내 공고
- '계약체결/낙찰' 정보 아님 - 순수 "입찰공고" 목록만 (이 API 자체가 공고 정보만 제공)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

API_BASE = "https://apis.data.go.kr/1230000/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# 수요기관명에 이 키워드가 포함된 공고만 남긴다 (서버가 필터를 무시할 경우를 대비해
# 클라이언트에서도 한 번 더 확인함)
INSTITUTION_KEYWORD = os.environ.get("G2B_INSTITUTION_KEYWORD", "해외")

LOOKBACK_DAYS = 183  # 약 6개월
ROWS_PER_PAGE = 100
MAX_PAGES = 30


def _fetch_page(page_no: int, begin_dt: str, end_dt: str, api_key: str) -> dict:
    params = {
        "ServiceKey": api_key,
        "type": "json",
        "inqryDiv": "1",           # 1 = 공고게시일시 기준 기간 검색
        "inqryBgnDt": begin_dt,    # YYYYMMDDHHMM
        "inqryEndDt": end_dt,
        "dminsttNm": INSTITUTION_KEYWORD,  # 수요기관명 (부분 검색)
        "pageNo": str(page_no),
        "numOfRows": str(ROWS_PER_PAGE),
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})

    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
        except Exception as e:
            last_err = e
            print(f"[나라장터 경고] page={page_no} 시도 {attempt + 1}/3 실패: {e}", file=sys.stderr)
            time.sleep(3)
    raise last_err


def fetch() -> list:
    api_key = os.environ.get("G2B_API_KEY", "").strip()
    if not api_key:
        print("[나라장터 경고] G2B_API_KEY 환경변수가 없어 건너뜁니다.", file=sys.stderr)
        return []

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    begin = now - timedelta(days=LOOKBACK_DAYS)
    begin_dt = begin.strftime("%Y%m%d0000")
    end_dt = now.strftime("%Y%m%d2359")

    results = {}

    for page in range(1, MAX_PAGES + 1):
        try:
            data = _fetch_page(page, begin_dt, end_dt, api_key)
        except Exception as e:
            print(f"[나라장터 경고] page={page} 요청 실패: {e}", file=sys.stderr)
            break

        body = data.get("response", {}).get("body", {})
        items_raw = body.get("items", [])
        # 결과가 1건일 때 dict로, 여러 건일 때 list로 오는 경우가 있어 방어적으로 처리
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not items_raw:
            break

        for item in items_raw:
            dminstt = item.get("dminsttNm", "") or ""
            if INSTITUTION_KEYWORD not in dminstt:
                continue  # 안전하게 클라이언트에서도 한 번 더 필터링

            nid = item.get("bidNtceNo", "") + "-" + item.get("bidNtceOrd", "")
            results[nid] = {
                "id": f"g2b-{nid}",
                "notice_type": "용역 입찰공고",
                "notice_date": item.get("bidNtceDt", ""),
                "submission_date": item.get("bidClseDt", ""),
                "country": "대한민국",
                "project_id": item.get("bidNtceNo", ""),
                "project_name": item.get("bidNtceNm", ""),
                "bid_reference_no": item.get("bidNtceNo", ""),
                "bid_description": dminstt,
                "procurement_method": item.get("cntrctCnclsMthdNm", ""),
                "summary": "",
                "source": "나라장터(G2B)",
                "source_url": item.get("bidNtceDtlUrl") or "https://www.g2b.go.kr",
            }

        total_count = int(body.get("totalCount", 0))
        if page * ROWS_PER_PAGE >= total_count:
            break
        time.sleep(0.2)

    return list(results.values())
