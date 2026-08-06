# -*- coding: utf-8 -*-
"""
조달청 나라장터 "입찰공고정보서비스" 공식 API 수집기.
공공데이터포털(data.go.kr)에서 발급받은 인증키가 필요하며,
환경변수 G2B_API_KEY 로 전달받는다 (GitHub Actions Secrets에서 주입).

조건 (사용자가 나라장터 사이트에서 직접 검색했던 조건과 동일하게 맞춤):
- 용역 분야 입찰공고
- 수요기관명에 "해외"가 포함된 공고만 (예: 한국해외인프라도시개발지원공사 등)
- 최근 3개월 이내 공고
- '계약체결/낙찰' 정보 아님 - 순수 "입찰공고" 목록만 (이 API 자체가 공고 정보만 제공)

※ 이 API는 한 번의 요청으로 조회 가능한 기간이 제한되어 있어("입력범위값 초과" 에러),
   전체 기간을 14일 단위로 잘라서 여러 번 나눠 요청한 뒤 결과를 합친다.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

from _country_extract import extract_country

API_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# 수요기관명에 이 키워드가 포함된 공고만 남긴다 (서버가 필터를 무시할 경우를 대비해
# 클라이언트에서도 한 번 더 확인함)
INSTITUTION_KEYWORD = os.environ.get("G2B_INSTITUTION_KEYWORD", "해외")

LOOKBACK_DAYS = 90  # 약 3개월
CHUNK_DAYS = 14      # 한 번에 조회할 기간 (API 제한을 피하기 위해 안전하게 14일)
ROWS_PER_PAGE = 100
MAX_PAGES_PER_CHUNK = 10


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
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
        except Exception as e:
            last_err = e
            print(f"[나라장터 경고] {begin_dt}~{end_dt} page={page_no} 시도 {attempt + 1}/2 실패: {e}", file=sys.stderr)
            time.sleep(2)
    raise last_err


def _date_chunks(total_days: int, chunk_days: int):
    """오늘부터 거꾸로 total_days 만큼을 chunk_days 단위로 잘라 (시작, 끝) 튜플 리스트로 반환."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    chunks = []
    end = now
    remaining = total_days
    while remaining > 0:
        span = min(chunk_days, remaining)
        begin = end - timedelta(days=span)
        chunks.append((begin, end))
        end = begin
        remaining -= span
    return chunks


def fetch() -> list:
    api_key = os.environ.get("G2B_API_KEY", "").strip()
    if not api_key:
        print("[나라장터 경고] G2B_API_KEY 환경변수가 없어 건너뜁니다.", file=sys.stderr)
        return []

    results = {}
    debug_printed = False
    consecutive_chunk_failures = 0
    MAX_CONSECUTIVE_FAILURES = 2

    for begin, end in _date_chunks(LOOKBACK_DAYS, CHUNK_DAYS):
        begin_dt = begin.strftime("%Y%m%d0000")
        end_dt = end.strftime("%Y%m%d2359")
        chunk_failed = False

        for page in range(1, MAX_PAGES_PER_CHUNK + 1):
            try:
                data = _fetch_page(page, begin_dt, end_dt, api_key)
            except Exception as e:
                print(f"[나라장터 경고] {begin_dt}~{end_dt} page={page} 요청 실패: {e}", file=sys.stderr)
                if page == 1:
                    chunk_failed = True
                break

            header = data.get("response", {}).get("header", {})
            result_code = header.get("resultCode", "")
            result_msg = header.get("resultMsg", "")
            if not debug_printed:
                raw_preview = json.dumps(data, ensure_ascii=False)[:500]
                print(f"[나라장터 디버그] 원본 응답 샘플: {raw_preview}", file=sys.stderr)
                debug_printed = True
            if result_code not in ("00", "0", ""):
                print(f"[나라장터 경고] {begin_dt}~{end_dt} API 오류: {result_code} - {result_msg}", file=sys.stderr)
                break

            body = data.get("response", {}).get("body", {})
            items_raw = body.get("items", [])
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
            if not items_raw:
                break

            for item in items_raw:
                dminstt = item.get("dminsttNm", "") or ""
                if INSTITUTION_KEYWORD not in dminstt:
                    continue

                nid = item.get("bidNtceNo", "") + "-" + item.get("bidNtceOrd", "")
                results[nid] = {
                    "id": f"g2b-{nid}",
                    "notice_type": "용역 입찰공고",
                    "notice_date": item.get("bidNtceDt", ""),
                    "submission_date": item.get("bidClseDt", ""),
                    "country": extract_country(item.get("bidNtceNm", "")),
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

        if chunk_failed:
            consecutive_chunk_failures += 1
            if consecutive_chunk_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[나라장터 경고] {MAX_CONSECUTIVE_FAILURES}개 구간 연속 실패 — 이번 실행은 여기서 포기하고 다음 소스로 넘어갑니다.", file=sys.stderr)
                break
        else:
            consecutive_chunk_failures = 0

        time.sleep(0.3)  # 청크 사이 서버 부담 방지

    return list(results.values())
