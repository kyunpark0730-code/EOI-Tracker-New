# -*- coding: utf-8 -*-
"""
ADB(아시아개발은행) 공식 RSS 피드 수집기.

csrn.adb.org(공고 상세 사이트)는 robots.txt로 자동 접근이 차단되어 있지만,
ADB가 공식적으로 제공하는 RSS 피드(feeds.feedburner.com, 전혀 다른 도메인)는
차단 대상이 아니며 동일한 공고 데이터를 담고 있다.
https://www.adb.org/rss 에 공식으로 안내된 피드 주소를 사용한다.
"""

import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

FEEDS = {
    "Consulting Services Recruitment Notice": "http://feeds.feedburner.com/adb-csrn",
    "Invitation for Bids": "http://feeds.feedburner.com/adb-invitation-for-bids",
    "Invitation for Prequalification": "http://feeds.feedburner.com/adb-invitation-for-prequalification",
    "Advanced Notice": "http://feeds.feedburner.com/adb-advanced-notices",
}

# 피드마다 담고 있는 기간 범위가 달라서(어떤 건 최근 것만, 어떤 건 과거 이력까지 섞여 있음),
# 최근 N일 이내 공고만 남기고 오래된 건 제외한다.
LOOKBACK_DAYS = 90


def _fetch_xml(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_category(category_text: str) -> dict:
    """'Date: 2026-04-28|Project Number: 57337-001|Status: Active|Countries: Nepal|Sectors: X'
    형식을 파싱한다."""
    fields = {}
    for part in (category_text or "").split("|"):
        if ":" in part:
            key, _, val = part.partition(":")
            fields[key.strip()] = val.strip()
    return fields


def fetch() -> list:
    results = []
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)

    for notice_type, feed_url in FEEDS.items():
        try:
            xml_text = _fetch_xml(feed_url)
            root = ET.fromstring(xml_text)
        except Exception as e:
            print(f"[ADB 경고] {notice_type} 피드 요청/파싱 실패: {e}", file=sys.stderr)
            continue

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            category_text = item.findtext("category") or ""
            fields = _parse_category(category_text)

            date_str = fields.get("Date", "")
            try:
                parsed = datetime.strptime(date_str, "%Y-%m-%d") if date_str else None
            except ValueError:
                parsed = None

            # 날짜를 모르거나(안전하게 제외), cutoff보다 오래된 공고는 건너뜀
            if parsed is None or parsed < cutoff:
                continue

            nid = guid or link or title
            results.append({
                "id": f"adb-{nid}",
                "notice_type": notice_type,
                "notice_date": date_str,
                "submission_date": "",
                "country": fields.get("Countries", ""),
                "project_id": fields.get("Project Number", ""),
                "project_name": title,
                "bid_reference_no": fields.get("Project Number", ""),
                "bid_description": fields.get("Sectors", ""),
                "procurement_method": "",
                "summary": "",
                "source": "ADB",
                "source_url": link,
                "_sort_date": parsed.isoformat(),
            })

    return results
