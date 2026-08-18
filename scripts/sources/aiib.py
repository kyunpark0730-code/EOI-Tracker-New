# -*- coding: utf-8 -*-
"""
AIIB(아시아인프라투자은행) 공식 RSS 피드 수집기 (로그인 불필요, 공개).
https://www.aiib.org/en/rss/index.html 에 공식으로 안내된 피드 주소를 사용한다.
※ 이 피드는 "공고"뿐 아니라 계약체결(Contract Award), 조달계획(Procurement Plan) 등
   서로 다른 성격의 문서가 섞여서 옵니다. notice_type은 파일명 등을 보고 최대한
   추정하지만 완벽하지 않을 수 있습니다.
"""
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from sources._country_extract import extract_country
FEED_URL = "https://www.aiib.org/en/rss/aiib-project-procurements-rss.xml"
LOOKBACK_DAYS = 45
def _fetch_xml(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EOI-Tracker/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")
def _parse_pubdate(raw: str):
    """'Aug 7, 2026' 또는 'Dec 30,2024'(쉼표 뒤 공백 없음) 등 형식을 유연하게 처리."""
    if not raw:
        return None
    cleaned = re.sub(r",\s*", ", ", raw.strip())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None
def _guess_notice_type(title: str, link: str) -> str:
    text = f"{title} {link}".lower()
    if "contract_award" in text or "noa-" in text or "notice of award" in text:
        return "Contract Award"
    if "ifb" in text or "invitation for bid" in text:
        return "Invitation for Bids"
    if "eoi" in text or "expression of interest" in text:
        return "Request for Expression of Interest"
    # "procurement-plan"이라는 완전한 문구뿐 아니라, AIIB가 파일명에 자주 쓰는
    # "PP-for-..."/"PP_for_..." 같은 약칭 패턴도 조달계획(Procurement Plan)으로 인식한다.
    if "procurement-plan" in text or "procurement_plan" in text:
        return "Procurement Plan"
    if re.search(r"(^|[\s/_\-])pp[-_]for[-_]", text) or re.search(r"(^|/)pp-", text):
        return "Procurement Plan"
    # "General Procurement Notice(GPN)"는 fetch_all.py의 분류 규칙이 "general
    # procurement" 문구로 "사전공개" 카테고리를 판별하므로, 그 문구가 그대로
    # 살아있는 값을 반환해야 한다 (그냥 "Procurement Notice"로 뭉뚱그리면 기타로 빠짐).
    if "general procurement notice" in text or re.search(r"(^|[\s/_\-])gpn([\s/_\-]|$)
        return "General Procurement Notice"
    return "Procurement Notice"
def _guess_country(link: str, title: str, description: str) -> str:
    # 링크 경로에 국가 폴더명이 영어로 들어있는 경우가 많음 (예: /Bangladesh/, /Kazakhstan/)
    m = re.search(r"/_download/([A-Za-z\- ]+)/", link)
    if m:
        return m.group(1).replace("-", " ")
    return extract_country(title, description)
def fetch() -> list:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=LOOKBACK_DAYS)
    results = {}
    try:
        xml_text = _fetch_xml(FEED_URL)
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"[AIIB 경고] 피드 요청/파싱 실패: {e}", file=sys.stderr)
        return []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()
        if not title or not link:
            continue
        parsed = _parse_pubdate(pub_date_raw)
        if parsed is None or parsed < cutoff:
            continue
        nid = link  # 링크(PDF 주소) 자체가 고유값 역할
        results[nid] = {
            "id": f"aiib-{nid}",
            "notice_type": _guess_notice_type(title, link),
            "notice_date": pub_date_raw,
            "submission_date": "",
            "country": _guess_country(link, title, description),
            "project_id": "",
            "project_name": title,
            "bid_reference_no": "",
            "bid_description": description,
            "procurement_method": "",
            "summary": description,
            "source": "AIIB",
            "source_url": link,
            "_sort_date": parsed.isoformat(),
        }
    return list(results.values())
