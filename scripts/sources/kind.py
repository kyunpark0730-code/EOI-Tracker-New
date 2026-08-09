# -*- coding: utf-8 -*-
"""
KIND(한국해외인프라도시개발지원공사) 입찰정보 게시판 수집기.
정적 HTML 게시판이라 requests + BeautifulSoup으로 파싱한다 (UTF-8, 로그인 불필요).
"""

import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

from sources._country_extract import extract_country

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

LIST_URL = "https://www.kindkorea.or.kr/pages/72"
DETAIL_BASE = "https://www.kindkorea.or.kr/pages/72"

LOOKBACK_DAYS = 60


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            print(f"[KIND 경고] 시도 {attempt + 1}/3 실패: {e}", file=sys.stderr)
            time.sleep(2)
    raise last_err


def fetch() -> list:
    if BeautifulSoup is None:
        print("[KIND 경고] beautifulsoup4가 설치되어 있지 않아 건너뜁니다.", file=sys.stderr)
        return []

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    results = []

    try:
        html = _fetch_html(LIST_URL)
    except Exception as e:
        print(f"[KIND 경고] 목록 페이지 요청 실패: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(html, "html.parser")

    matched_links = soup.find_all("a", href=re.compile(r"[?&]id=\d+.*menuMode=READ"))
    print(f"[KIND 디버그] HTML 길이={len(html)}, 매칭된 링크 수={len(matched_links)}", file=sys.stderr)
    if not matched_links:
        # 패턴이 안 맞을 경우를 대비해, id= 만 들어간 링크가 있는지도 확인
        any_id_links = soup.find_all("a", href=re.compile(r"[?&]id=\d+"))
        print(f"[KIND 디버그] id= 만 포함된 링크 수={len(any_id_links)}", file=sys.stderr)
        if any_id_links:
            print(f"[KIND 디버그] 예시 href: {any_id_links[0].get('href')}", file=sys.stderr)

    skipped_no_date = 0
    skipped_old = 0

    for link in matched_links:
        href = link.get("href", "")
        id_match = re.search(r"[?&]id=(\d+)", href)
        if not id_match:
            continue
        notice_id = id_match.group(1)

        title = link.get_text(strip=True)
        if not title:
            continue

        # <tr>가 아닐 수도 있으므로, 상위로 올라가며 날짜 패턴이 보이는 첫 컨테이너를 찾는다
        date_match = None
        node = link
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            m = re.search(r"\d{4}-\d{2}-\d{2}", node.get_text())
            if m:
                date_match = m
                break

        notice_date = date_match.group(0) if date_match else ""

        parsed_date = None
        if notice_date:
            try:
                parsed_date = datetime.strptime(notice_date, "%Y-%m-%d")
            except ValueError:
                parsed_date = None
        else:
            skipped_no_date += 1

        if parsed_date and parsed_date < cutoff:
            skipped_old += 1
            continue  # 오래된 공고는 제외

        # 대괄호 안 공고 유형([입찰공고 26-28호], [사전규격 공개] 등) 추출
        type_match = re.match(r"\[([^\]]+)\]", title)
        notice_type = type_match.group(1) if type_match else "입찰정보"

        results.append({
            "id": f"kind-{notice_id}",
            "notice_type": notice_type,
            "notice_date": notice_date,
            "submission_date": "",
            "country": extract_country(title),
            "project_id": notice_id,
            "project_name": title,
            "bid_reference_no": "",
            "bid_description": "",
            "procurement_method": "",
            "summary": "",
            "source": "KIND",
            "source_url": f"{DETAIL_BASE}?id={notice_id}&menuMode=READ&q=",
        })

    print(f"[KIND 디버그] 최종 {len(results)}건 (날짜못찾음 {skipped_no_date}건, 오래된공고 제외 {skipped_old}건)", file=sys.stderr)
    return results
