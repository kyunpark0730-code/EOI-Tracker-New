#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
등록된 모든 소스(sources/*.py)의 fetch()를 호출해서 결과를 합치고,
data/notices.json 으로 저장하는 오케스트레이터.

새 사이트를 추가하려면:
  1. scripts/sources/<이름>.py 파일을 만들고 fetch() -> list[dict] 함수를 구현
     (공통 스키마는 scripts/sources/worldbank.py 또는 ekacem.py 참고)
  2. 아래 SOURCES 리스트에 모듈을 추가
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from sources import worldbank, ekacem, adb, g2b, icak, eib, kind  # noqa: E402

SOURCES = [
    ("World Bank", worldbank),
    ("한국건설엔지니어링협회", ekacem),
    ("ADB", adb),
    ("나라장터(G2B)", g2b),
    ("해외건설협회(ICAK)", icak),
    ("EIB", eib),
    ("KIND", kind),
]


def main():
    all_notices = []
    summary = []

    for label, module in SOURCES:
        try:
            items = module.fetch()
        except Exception as e:
            print(f"[경고] {label} 수집 중 오류: {e}", file=sys.stderr)
            items = []
        print(f"{label}: {len(items)}건 수집")
        summary.append(f"{label} {len(items)}건")
        all_notices.extend(items)

    def sort_key(n):
        return n.get("_sort_date") or ""

    all_notices.sort(key=sort_key, reverse=True)
    for n in all_notices:
        n.pop("_sort_date", None)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": summary,
        "count": len(all_notices),
        "notices": all_notices,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "notices.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"전체 수집 완료: {len(all_notices)}건 -> {out_path}")


if __name__ == "__main__":
    main()
