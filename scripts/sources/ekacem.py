# -*- coding: utf-8 -*-
"""
한국건설엔지니어링협회(ekacem) 입찰공고 게시판 수집기.
정적 HTML 게시판이라 requests + BeautifulSoup으로 파싱한다.
페이지는 EUC-KR 인코딩이므로 명시적으로 디코딩한다.
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

LIST_URL = "http://www.ekacem.or.kr/news/bid_li.asp"
DETAIL_BASE = "http://www.ekacem.or.kr/news/"

# 최근 N일 이내에 등록된 공고만 (이 게시판엔 별도 마감일 필드가 없어 등록일 기준으로 필터)
LOOKBACK_DAYS = 30


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)",
        "Connection": "close",
    })
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()
            break
        except Exception as e:
            last_err = e
            print(f"[ekacem 경고] 시도 {attempt + 1}/3 실패: {e}", file=sys.stderr)
            time.sleep(2)
    else:
        raise last_err
    for enc in ("euc-kr", "cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("euc-kr", errors="replace")


def fetch() -> list:
    if BeautifulSoup is None:
        print("[ekacem 경고] beautifulsoup4가 설치되어 있지 않아 건너뜁니다.", file=sys.stderr)
        return []

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    results = []

    try:
        html = _fetch_html(LIST_URL)
    except Exception as e:
        print(f"[ekacem 경고] 목록 페이지 요청 실패: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(html, "html.parser")

    # 'bid_vi.asp?num=' 링크가 있는 행만 대상으로, 각 행에서 날짜/분류/제목 추출
    for link in soup.find_all("a", href=re.compile(r"bid_vi\.asp\?num=\d+")):
        row = link.find_parent("tr")
        if row is None:
            continue

        cells = row.find_all("td")
        cell_texts = [c.get_text(strip=True) for c in cells]

        # 날짜(YYYY-MM-DD 패턴)를 행 전체 텍스트에서 탐색
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", row.get_text())
        notice_date = date_match.group(0) if date_match else ""

        parsed_date = None
        if notice_date:
            try:
                parsed_date = datetime.strptime(notice_date, "%Y-%m-%d")
            except ValueError:
                parsed_date = None

        if parsed_date and parsed_date < cutoff:
            continue  # 오래된 공고는 제외

        num_match = re.search(r"num=(\d+)", link.get("href", ""))
        num = num_match.group(1) if num_match else None
        if not num:
            continue

        title = link.get_text(strip=True)
        # 분류(카테고리)는 보통 날짜 다음 셀에 위치
        category = ""
        for t in cell_texts:
            if t and t != notice_date and t != title and not t.isdigit():
                category = t
                break

        results.append({
            "id": f"ekacem-{num}",
            "notice_type": category or "입찰공고",
            "notice_date": notice_date,
            "submission_date": "",
            "country": extract_country(title),
            "project_id": "",
            "project_name": title,
            "bid_reference_no": "",
            "bid_description": "",
            "procurement_method": "",
            "summary": "",
            "source": "한국건설엔지니어링협회",
            "source_url": f"{DETAIL_BASE}bid_vi.asp?num={num}",
            "_sort_date": (parsed_date or datetime.min).isoformat(),
        })

    return results
