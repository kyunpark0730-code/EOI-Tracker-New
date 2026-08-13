#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
등록된 모든 소스(sources/*.py)의 fetch()를 호출해서 결과를 합치고,
data/notices.json 으로 저장하는 오케스트레이터.

새 사이트를 추가하려면:
  1. scripts/sources/<이름>.py 파일을 만들고 fetch() -> list[dict] 함수를 구현
     (공통 스키마는 scripts/sources/worldbank.py 또는 ekacem.py 참고)
  2. 아래 SOURCES 리스트에 모듈을 추가

[안전장치] 특정 소스가 그날 0건을 반환하면(예: 나라장터처럼 간헐적으로
타임아웃 나는 소스), 그 소스만 "실패"로 보고 직전 성공 실행 때 수집했던
해당 소스의 데이터를 그대로 유지합니다. 대신 소스별 마지막 성공 갱신일과
연속 실패 횟수를 data/notices.json 의 "source_status"에 기록해서, 오래
갱신되지 않은 소스가 있으면 대시보드에서 알아볼 수 있게 합니다.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from sources import worldbank, ekacem, adb, g2b, icak, eib, kind, aiib  # noqa: E402
from sources._sector_filter import (  # noqa: E402
    is_relevant, is_individual_job_posting, is_risk_country,
    HARD_EXCLUDE_PATTERNS,
)

# 코드가 최신 버전으로 실제 반영됐는지 로그 맨 앞에서 바로 확인할 수 있게 하는
# 지문(fingerprint). 이 줄이 로그에 없거나 개수가 다르면, GitHub에 커밋된 파일이
# 최신본이 아니라는 뜻이다.
print(f"[버전 확인] HARD_EXCLUDE_PATTERNS {len(HARD_EXCLUDE_PATTERNS)}개 로드됨 "
      f"(RAP 테스트: {'제외됨' if is_relevant('Resettlement Action Plan Road') is False else '제외 안 됨(구버전 의심)'})")

# 소스마다(영어/프랑스어/한국어) 제각각인 notice_type 원문을 5개 통합 카테고리로
# 정리한다. 사전 매칭 대신 키워드 패턴으로 판단해서, 새 소스가 추가되거나
# 예상 못 한 값이 들어와도(예: "입찰공고 26-027호"처럼 번호가 붙은 값) 자동으로
# 적절한 카테고리에 묶이게 한다.
_NOTICE_TYPE_RULES = [
    ("관심표명(EOI)", ["expression of interest", "관심표명", "manifestation d'int", "manifestation d’int"]),
    ("제안요청(RFP)", ["request for proposal", "제안요청", "demande de proposition"]),
    ("사전공개", ["general procurement", "사전규격", "사전공개", "prior information", "avis general"]),
    ("입찰공고", ["bid", "tender", "prequalification", "입찰", "appel d'offres", "appel doffres"]),
]

# 낙찰결과(Contract Award)는 이미 끝난 결과 통보라 지원 기회가 아니므로,
# 카테고리로 분류하지 않고 아예 수집 단계에서 제외한다 (아래 _is_contract_award 참고).
_CONTRACT_AWARD_KEYWORDS = ["award", "낙찰", "계약체결", "attribution"]


def _is_contract_award(raw: str) -> bool:
    if not raw:
        return False
    low = raw.lower()
    return any(kw in low for kw in _CONTRACT_AWARD_KEYWORDS)


def _is_procurement_plan(raw: str) -> bool:
    """조달계획(Procurement Plan)은 개별 지원 가능한 공고가 아니라 사업 전체의
    계약 목록을 미리 정리해둔 참고용 문서라(대부분 개인 컨설턴트 채용이거나 이미
    완료(Cleared)된 항목들), 낙찰결과와 마찬가지로 아예 수집 단계에서 제외한다."""
    if not raw:
        return False
    return raw.strip().lower() == "procurement plan"


def normalize_notice_type(raw: str) -> str:
    if not raw:
        return "기타"
    low = raw.lower()
    for category, keywords in _NOTICE_TYPE_RULES:
        if any(kw in low for kw in keywords):
            return category
    return "기타"


# 재무/거래자문(Transaction Advisory) 등 다산 전문영역 밖의 업무가, 타당성조사/설계 같은
# 진짜 관련 업무랑 "하나의 계약"으로 묶여 있으면 컨소시엄 파트너가 필요할 가능성이 높다.
# (예: "Phase 1: Feasibility Study, Phase 2: Transaction Advisory Services"처럼
# 도로 타당성조사만 하고 싶어도 그 뒤에 딸린 재무자문까지 통째로 계약해야 하는 경우)
_NON_ENGINEERING_ADVISORY_KEYWORDS = [
    "transaction advisory", "financial advisory", "legal advisory",
    "ppp advisory", "public private partnership", "public-private partnership",
]


def has_consortium_signal(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t).lower()
    if not combined:
        return False
    has_advisory = any(kw in combined for kw in _NON_ENGINEERING_ADVISORY_KEYWORDS)
    has_multi_phase = ("phase 1" in combined or "phase i " in combined) and \
        ("phase 2" in combined or "phase ii " in combined)
    return has_advisory or has_multi_phase

# 교통수요조사(Traffic Count/Origin-Destination/Willingness-to-Pay 등)는 설계·감리
# 없이 단독 용역으로 나올 때가 있는데, 이건 교통계획/경제분석 전문영역이라 다산의
# 주력(설계/감리)이랑 결이 다를 수 있다. 다만 종합 타당성조사 패키지 안에 세부
# 과업으로 포함되는 경우도 흔해서 무조건 제외하지는 않고, 배지로만 표시해서
# 사람이 직접 판단하게 한다 (라이베리아 톨게이트 WTP 조사 사례를 계기로 만듦).
_TRAFFIC_SURVEY_KEYWORDS =  [ 
    "willingness-to-pay", "willingness to pay", "origin-destination survey",
    "origin-destination survey", "stated preference", "traffic count survey",
    "toll rate recommendation",
]


def has_traffic_survey_signal(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t).lower()
    if not combined:
        return False
    return any(kw in combined for kw in _TRAFFIC_SURVEY_KEYWORDS)

SOURCES = [
    ("World Bank", worldbank),
    ("한국건설엔지니어링협회", ekacem),
    ("ADB", adb),
    ("나라장터(G2B)", g2b),
    ("해외건설협회(ICAK)", icak),
    ("EIB", eib),
    ("KIND", kind),
    ("AIIB", aiib),
]

# 연속 실패가 이 횟수 이상 누적되면 로그에 강조 경고를 남긴다.
CONSECUTIVE_FAILURE_ALERT_THRESHOLD = 5

KST = timezone(timedelta(hours=9))
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "notices.json")


def _load_previous_data():
    """이전 data/notices.json 전체를 읽어온다. 없거나 손상됐으면 빈 기본값."""
    if not os.path.exists(OUT_PATH):
        return {}
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_previous_first_seen(old_data):
    """이전 데이터에서 공고 id -> 첫 발견일(first_seen) 매핑을 읽어온다.
    처음 보는 공고는 나중에 오늘 날짜로 채워지고, 기존에 있었지만 first_seen 기록이
    없던 공고(이 기능 도입 이전 데이터)는 '예전 실행 시점에라도 이미 있었던 것'으로
    간주해 이전 generated_at 날짜를 대신 넣어준다 (오늘 신규로 잘못 표시되는 것 방지)."""
    fallback_date = None
    old_generated_at = old_data.get("generated_at")
    if old_generated_at:
        fallback_date = old_generated_at[:10]

    mapping = {}
    for n in old_data.get("notices", []):
        nid = n.get("id")
        if not nid:
            continue
        mapping[nid] = n.get("first_seen") or fallback_date
    return mapping


def _load_previous_source_items(old_data):
    """이전 data/notices.json에서 소스 라벨별 공고 목록을 복원한다.
    (오늘 실행에서 그 소스가 실패했을 때 대체용으로 쓰기 위함)"""
    by_source = {}
    for n in old_data.get("notices", []):
        src = n.get("_source_label")
        if not src:
            continue
        by_source.setdefault(src, []).append(n)
    return by_source


def main():
    today_kst = datetime.now(KST).strftime("%Y-%m-%d")
    old_data = _load_previous_data()
    previous_first_seen = _load_previous_first_seen(old_data)
    previous_source_items = _load_previous_source_items(old_data)
    previous_source_status = old_data.get("source_status", {})

    all_notices = []
    summary = []
    source_status = {}

    for label, module in SOURCES:
        prev_status = previous_source_status.get(label, {})
        try:
            items = module.fetch()
        except Exception as e:
            print(f"[경고] {label} 수집 중 오류: {e}", file=sys.stderr)
            items = []

        if items:
            # 이번 실행 성공: 마지막 성공일 갱신, 연속 실패 카운트 초기화
            for n in items:
                n["_source_label"] = label
            print(f"{label}: {len(items)}건 수집")
            source_status[label] = {
                "last_success": today_kst,
                "consecutive_failures": 0,
            }
        else:
            # 이번 실행 실패(0건): 직전 성공 데이터로 대체하고 실패 카운트 누적
            fallback_items = previous_source_items.get(label, [])
            items = fallback_items
            consecutive = prev_status.get("consecutive_failures", 0) + 1
            last_success = prev_status.get("last_success", "알 수 없음")
            source_status[label] = {
                "last_success": last_success,
                "consecutive_failures": consecutive,
            }
            print(
                f"{label}: 이번 실행 0건 -> 이전 데이터 유지 "
                f"({len(fallback_items)}건, 마지막 성공: {last_success}, "
                f"연속 실패 {consecutive}회)"
            )
            if consecutive >= CONSECUTIVE_FAILURE_ALERT_THRESHOLD:
                print(
                    f"[!!경고!!] {label} 이(가) {consecutive}일 연속 수집 실패 중입니다. "
                    f"일시적 문제가 아닐 수 있으니 원인을 다시 점검하세요.",
                    file=sys.stderr,
                )

        summary.append(f"{label} {len(items)}건")
        all_notices.extend(items)

    def sort_key(n):
        return n.get("_sort_date") or ""

    all_notices.sort(key=sort_key, reverse=True)

    before_filter = len(all_notices)

    # World Bank는 procurement_group 필드로 물품(Goods)/공사(Civil Works)/컨설팅
    # 용역(Consulting Services) 등을 명확히 구분해서 준다. 다산은 컨설팅 용역만
    # 참여하므로, 다른 소스에는 없는 이 필드가 "GO"(물품 조달)나 "CW"(공사, 시공사가
    # 입찰하는 건)인 경우는 텍스트 키워드 판단 없이 확실하게 제외한다.
    # NC = Non-Consulting Services(비컨설팅 용역: 행사관리, 경비, 청소 등) —
    # 다산은 컨설팅 용역(CS)만 하므로 GO/CW와 마찬가지로 통째로 제외한다.
    EXCLUDED_PROCUREMENT_GROUPS = {"GO", "CW", "NC"}
    before_goods_filter = len(all_notices)
    all_notices = [n for n in all_notices if n.get("procurement_group") not in EXCLUDED_PROCUREMENT_GROUPS]
    goods_filtered_out = before_goods_filter - len(all_notices)
    print(f"물품/공사/비컨설팅용역(Goods/CW/NC)으로 제외됨: {goods_filtered_out}건")

    # 낙찰결과(Contract Award)는 이미 끝난 결과 통보라 지원 기회가 아니므로 통째로 제외한다.
    before_award_filter = len(all_notices)
    all_notices = [n for n in all_notices if not _is_contract_award(n.get("notice_type", ""))]
    award_filtered_out = before_award_filter - len(all_notices)
    print(f"낙찰결과(Contract Award)로 제외됨: {award_filtered_out}건")

    # 조달계획(Procurement Plan)도 개별 지원 공고가 아니므로 통째로 제외한다.
    before_pp_filter = len(all_notices)
    all_notices = [n for n in all_notices if not _is_procurement_plan(n.get("notice_type", ""))]
    pp_filtered_out = before_pp_filter - len(all_notices)
    print(f"조달계획(Procurement Plan)으로 제외됨: {pp_filtered_out}건")

    before_job_filter = len(all_notices)

    def _job_title_text(n):
        # World Bank 등 일부 소스는 실제 직책명이 project_name(사업명 전체)이 아니라
        # bid_description(과업/직책 제목) 필드에 따로 저장된다. 있으면 그걸 우선 검사하고,
        # 없으면 기존처럼 project_name을 검사한다.
        return n.get("bid_description") or n.get("project_name", "")

    def _is_job_posting(n):
        # World Bank는 procurement_method 필드에 언어 무관하게 항상 영어로
        # "Individual Consultant Selection"이라고 명시해준다 (참조번호의 CS-INDV와
        # 대응). 공고 원문이 프랑스어/포르투갈어/스페인어라 제목 정규식으로는
        # 못 잡는 채용공고도, 이 필드로는 언어와 상관없이 확실하게 잡아낼 수 있다.
        method = (n.get("procurement_method") or "").lower()
        if "individual consultant" in method:
            return True
        return is_individual_job_posting(_job_title_text(n))

    all_notices = [n for n in all_notices if not _is_job_posting(n)]
    job_filtered_out = before_job_filter - len(all_notices)
    print(f"채용(개인 직책) 공고로 제외됨: {job_filtered_out}건")

    all_notices = [
        n for n in all_notices
        if is_relevant(n.get("project_name", ""), n.get("bid_description", ""),
                        n.get("notice_type", ""), n.get("summary", ""))
    ]
    filtered_out = before_filter - len(all_notices) - job_filtered_out - goods_filtered_out - award_filtered_out - pp_filtered_out
    print(f"분야 필터로 제외됨: {filtered_out}건 (관개/도로/수자원 등과 무관)")

    # 위험국/분쟁국(소말리아, 아프가니스탄, 우크라이나 등 - 실제 출장이 어려운 국가)은
    # 핵심 인프라 키워드가 있어도 예외 없이 무조건 제외한다.
    # (이전엔 "확실한 인프라 키워드가 있으면 유지"하는 예외를 뒀었지만, 우크라이나의
    # 진짜 수자원 인프라 사업까지 노출되는 문제가 있어 이 예외를 없앴다.)
    before_risk_filter = len(all_notices)
    all_notices = [n for n in all_notices if not is_risk_country(n.get("country", ""))]
    risk_filtered_out = before_risk_filter - len(all_notices)
    print(f"위험국으로 제외됨: {risk_filtered_out}건")

    new_today_count = 0
    for n in all_notices:
        n.pop("_sort_date", None)
        n["notice_type_normalized"] = normalize_notice_type(n.get("notice_type", ""))
        n["consortium_signal"] = has_consortium_signal(
            n.get("project_name", ""), n.get("bid_description", ""), n.get("summary", "")
        )
        n["traffic_survey_signal"] = has_traffic_survey_signal (
             n.get("project_name", ""), n.get("bid_description", ""), n.get("summary",
        )
        nid = n.get("id")
        first_seen = previous_first_seen.get(nid) or today_kst
        n["first_seen"] = first_seen
        if first_seen == today_kst:
            new_today_count += 1

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today_kst": today_kst,
        "sources": summary,
        "source_status": source_status,
        "count": len(all_notices),
        "new_today_count": new_today_count,
        "notices": all_notices,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"전체 수집 완료: {len(all_notices)}건 (오늘 신규 {new_today_count}건) -> {OUT_PATH}")


if __name__ == "__main__":
    main()
