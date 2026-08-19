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

※ 나라장터 서버 자체가 GitHub Actions IP대역을 간헐적으로 막는 문제가 있어(자세한
   내용은 프로젝트 메모 참고), 실패할 때 워크플로 전체 실행시간을 크게 잡아먹지
   않도록 타임아웃을 짧게(15초) 잡아둔다. 재시도 2회는 유지 — 완전 차단이 아니라
   순간적인 서버 부하일 가능성도 있어서 한 번은 더 기회를 준다.

※ [캐시 폴백] "복불복" 특성상 매일 1회 정기 실행 시점엔 실패해도, 하루 중 다른
   시점(g2b-retry 워크플로, 4시간마다 별도 실행)엔 성공했을 수 있다. 그 성공
   결과를 data/g2b_cache.json에 저장해두고, 이번 실행이 실패(0건)하면 그 캐시를
   대신 사용한다 — "어제 데이터"보다 훨씬 최신인 "몇 시간 전 성공 데이터"를 쓸 수
   있어 더 정확하다.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

from sources._country_extract import extract_country

API_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# 수요기관명에 이 키워드들 중 하나라도 포함된 공고를 남긴다 (여러 개 지원).
# "해외" = 해외인프라/해외건설 관련 기관, "국제협력단" = KOICA(한국국제협력단, 최근 조달을
# 나라장터로 완전히 이전함)
_default_keywords = "해외,국제협력단"
INSTITUTION_KEYWORDS = [
    k.strip() for k in os.environ.get("G2B_INSTITUTION_KEYWORD", _default_keywords).split(",")
    if k.strip()
]

LOOKBACK_DAYS = 90  # 약 3개월
CHUNK_DAYS = 14      # 한 번에 조회할 기간 (API 제한을 피하기 위해 안전하게 14일)
ROWS_PER_PAGE = 100
MAX_PAGES_PER_CHUNK = 10
REQUEST_TIMEOUT_SECONDS = 15  # 기존 45초 → 15초로 단축 (실패시 워크플로 시간 절약)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "g2b_cache.json")


def _fetch_page(page_no: int, begin_dt: str, end_dt: str, api_key: str, institution_keyword: str) -> dict:
    params = {
        "ServiceKey": api_key,
        "type": "json",
        "inqryDiv": "1",           # 1 = 공고게시일시 기준 기간 검색
        "inqryBgnDt": begin_dt,    # YYYYMMDDHHMM
        "inqryEndDt": end_dt,
        "dminsttNm": institution_keyword,  # 수요기관명 (부분 검색)
        "pageNo": str(page_no),
        "numOfRows": str(ROWS_PER_PAGE),
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})

    last_err = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
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


def _fetch_live() -> list:
    """나라장터 API를 실제로 호출해서 결과를 가져온다 (캐시 폴백 없이 순수 시도만)."""
    api_key = os.environ.get("G2B_API_KEY", "").strip()
    if not api_key:
        print("[나라장터 경고] G2B_API_KEY 환경변수가 없어 건너뜁니다.", file=sys.stderr)
        return []

    results = {}
    debug_printed = False

    for institution_keyword in INSTITUTION_KEYWORDS:
        consecutive_chunk_failures = 0
        MAX_CONSECUTIVE_FAILURES = 2

        for begin, end in _date_chunks(LOOKBACK_DAYS, CHUNK_DAYS):
            begin_dt = begin.strftime("%Y%m%d0000")
            end_dt = end.strftime("%Y%m%d2359")
            chunk_failed = False

            for page in range(1, MAX_PAGES_PER_CHUNK + 1):
                try:
                    data = _fetch_page(page, begin_dt, end_dt, api_key, institution_keyword)
                except Exception as e:
                    print(f"[나라장터 경고][{institution_keyword}] {begin_dt}~{end_dt} page={page} 요청 실패: {e}", file=sys.stderr)
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
                    print(f"[나라장터 경고][{institution_keyword}] {begin_dt}~{end_dt} API 오류: {result_code} - {result_msg}", file=sys.stderr)
                    break

                body = data.get("response", {}).get("body", {})
                items_raw = body.get("items", [])
                if isinstance(items_raw, dict):
                    items_raw = [items_raw]
                if not items_raw:
                    break

                for item in items_raw:
                    dminstt = item.get("dminsttNm", "") or ""
                    if institution_keyword not in dminstt:
                        continue

                    nid = item.get("bidNtceNo", "") + "-" + item.get("bidNtceOrd", "")
                    # 수요기관명에 "국제협력단"이 있으면 KOICA(한국국제협력단) 공고임을
                    # 대시보드에서 바로 알아볼 수 있도록 별도 태그로 표시한다.
                    agency_tag = "KOICA" if "국제협력단" in dminstt else ""
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
                        "agency_tag": agency_tag,
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
                    print(f"[나라장터 경고][{institution_keyword}] {MAX_CONSECUTIVE_FAILURES}개 구간 연속 실패 — 이 키워드는 여기서 포기하고 다음으로 넘어갑니다.", file=sys.stderr)
                    break
            else:
                consecutive_chunk_failures = 0

            time.sleep(0.3)  # 청크 사이 서버 부담 방지

    return list(results.values())


def save_cache(items: list) -> None:
    """성공한 결과를 캐시 파일에 저장한다 (g2b-retry 워크플로 전용 진입점)."""
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "notices": items,
    }
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _load_cache() -> list:
    if not os.path.exists(CACHE_PATH):
        return []
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return []
    fetched_at = payload.get("fetched_at", "알 수 없음")
    items = payload.get("notices", [])
    if items:
        print(f"[나라장터] 이번 실행은 실패, 캐시(성공 시점: {fetched_at})로 대체 — {len(items)}건", file=sys.stderr)
    return items


def _parse_dt(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _drop_expired(items: list) -> list:
    """G2B API는 World Bank와 달리 '공고 게시일' 기준으로 최근 90일치를 가져오기
    때문에(마감일 기준이 아님), 이미 제출기한이 지난 공고도 그대로 섞여 들어온다.
    특히 특정 기간 구간이 여러 날 실패하다가 뒤늦게 한 번 성공하면, 이미 마감된
    공고가 "오늘 신규"로 잘못 표시되는 문제가 있었다. World Bank처럼 마감일이
    지나지 않은 공고만 남긴다 (마감일 정보가 없거나 파싱 실패하면 안전하게 유지)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    active = []
    dropped = 0
    for it in items:
        deadline = _parse_dt(it.get("submission_date", ""))
        if deadline is not None and deadline < now:
            dropped += 1
            continue
        active.append(it)
    if dropped:
        print(f"[나라장터] 마감 지난 공고 {dropped}건 제외", file=sys.stderr)
    return active


def fetch() -> list:
    """메인 오케스트레이터(fetch_all.py)가 부르는 진입점. 실시간 시도 후,
    실패(0건)하면 최근 성공했던 캐시로 자동 대체한다."""
    items = _fetch_live()
    if not items:
        items = _load_cache()
    return _drop_expired(items)
