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
from sources._sector_filter import is_relevant, is_individual_job_posting  # noqa: E402

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

    before_job_filter = len(all_notices)

    def _job_title_text(n):
        # World Bank 등 일부 소스는 실제 직책명이 project_name(사업명 전체)이 아니라
        # bid_description(과업/직책 제목) 필드에 따로 저장된다. 있으면 그걸 우선 검사하고,
        # 없으면 기존처럼 project_name을 검사한다.
        return n.get("bid_description") or n.get("project_name", "")

    all_notices = [n for n in all_notices if not is_individual_job_posting(_job_title_text(n))]
    job_filtered_out = before_job_filter - len(all_notices)
    print(f"채용(개인 직책) 공고로 제외됨: {job_filtered_out}건")

    all_notices = [
        n for n in all_notices
        if is_relevant(n.get("project_name", ""), n.get("bid_description", ""),
                        n.get("notice_type", ""), n.get("summary", ""))
    ]
    filtered_out = before_filter - len(all_notices) - job_filtered_out
    print(f"분야 필터로 제외됨: {filtered_out}건 (관개/도로/수자원 등과 무관)")

    new_today_count = 0
    for n in all_notices:
        n.pop("_sort_date", None)
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
