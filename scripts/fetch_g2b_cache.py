#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나라장터(G2B) 전용 재시도 스크립트. g2b-retry 워크플로에서 4시간마다 실행된다.

메인 fetch_all.py(매일 1회)와 별개로 하루 여러 번 나라장터만 따로 시도해서,
성공하면 그 결과를 data/g2b_cache.json에 저장해둔다. GitHub Actions는 실행마다
IP가 바뀌기 때문에, 시도 횟수를 늘리면 "운 좋은 IP"에 걸릴 확률이 올라간다.

메인 fetch_all.py 실행 시점에 나라장터가 마침 실패해도, g2b.py의 fetch()가
이 캐시 파일을 자동으로 대신 사용한다 (g2b.py의 _load_cache 참고).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sources import g2b  # noqa: E402


def main():
    items = g2b._fetch_live()
    if not items:
        print("[나라장터 재시도] 이번 시도도 실패 — 캐시 갱신 안 함 (기존 캐시 유지)")
        return
    g2b.save_cache(items)
    print(f"[나라장터 재시도] 성공! {len(items)}건 수집 -> data/g2b_cache.json 갱신")


if __name__ == "__main__":
    main()
