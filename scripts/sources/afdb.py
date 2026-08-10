# -*- coding: utf-8 -*-
"""
AfDB(아프리카개발은행) 공식 RSS 피드 수집기 (로그인 불필요, 공개).
https://www.afdb.org/en/rss-feeds 에 공식으로 안내된 피드 주소를 사용한다.

※ 실제 필드 구조를 사전에 확인하지 못해, 표준 RSS 필드(title/link/pubDate/description)를
   최대한 유연하게 파싱하도록 작성함. 최초 실행 결과를 보고 조정이 필요할 수 있음.
"""

import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

from sources._country_extract import extract_country

# "Current Solicitations" 피드로 변경 (procurement.xml이 403으로 막혀서 다른 경로 시도)
FEED_URL = "https://www.afdb.org/en/about-us/corporate-procurement/procurement-notices/current-solicitations.xml"
LOOKBACK_DAYS = 45

DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",   # RFC 822 (표준 RSS pubDate)
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%d",
    "%d %b %Y",
    "%b %d, %Y",
)


def _fetch_xml(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.afdb.org/en/projects-and-operations/procurement",
    })
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            print(f"[AfDB 경고] 시도 {attempt + 1}/3 실패: {e}", file=sys.stderr)
            time.sleep(3)
    raise last_err


def _parse_date(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=None)
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


def fetch() -> list:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    results = {}

    try:
        xml_text = _fetch_xml(FEED_URL)
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[AfDB 경고] 피드 요청/파싱 실패: {e}", file=sys.stderr)
        return []

    items = root.findall(".//item")
    print(f"[AfDB 디버그] 피드 항목 수: {len(items)}", file=sys.stderr)

    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        description = _strip_html(item.findtext("description") or "")

        if not title or not link:
            continue

        parsed = _parse_date(pub_date_raw)
        if parsed is None or parsed < cutoff:
            continue

        # 제목이 보통 "GPN - Kenya - ..." / "SPN - Eritrea - ..." 형식이라 앞부분에서 유형/국가 추출
        parts = [p.strip() for p in title.split(" - ")]
        type_match = re.match(r"^(GPN|SPN|EOI|IFB|RFP|REOI)$", parts[0], re.IGNORECASE) if parts else None
        notice_type = parts[0].upper() if type_match else "Procurement Notice"
        country = parts[1] if type_match and len(parts) > 1 else extract_country(title, description)

        nid = link
        results[nid] = {
            "id": f"afdb-{nid}",
            "notice_type": notice_type,
            "notice_date": pub_date_raw,
            "submission_date": "",
            "country": country,
            "project_id": "",
            "project_name": title,
            "bid_reference_no": "",
            "bid_description": description[:300],
            "procurement_method": "",
            "summary": description,
            "source": "AfDB",
            "source_url": link,
            "_sort_date": parsed.isoformat(),
        }

    return list(results.values())
