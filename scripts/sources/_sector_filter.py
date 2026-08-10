# -*- coding: utf-8 -*-
"""
다산컨설턴트의 핵심 관심 분야(관개, 도로, 수자원 등 토목 인프라)와 확실히 무관한
공고를 걸러내는 공통 필터.

원칙: "애매하면 살린다." 관련 키워드가 하나라도 있으면 무조건 포함시키고,
관련 키워드가 전혀 없고 명백히 무관한 키워드(AI, 건축설계, 보건, 교육 등)만
있는 경우에만 제외한다. 판단이 애매한(둘 다 없는) 경우는 기본적으로 포함한다.
"""

import re

# 하나라도 걸리면 무조건 포함 (토목/인프라 핵심 분야)
INCLUDE_PATTERNS = [
    r"irrigation", r"관개",
    r"\broad\b", r"highway", r"도로",
    r"water resource", r"water supply", r"수자원", r"상수도", r"용수",
    r"\bdam\b", r"댐",
    r"bridge", r"교량",
    r"drainage", r"배수",
    r"flood", r"홍수",
    r"transport", r"교통",
    r"hydro", r"수력",
    r"canal", r"수로",
    r"sewer", r"하수",
    r"embankment", r"제방",
    r"reservoir", r"저수지",
    r"civil engineering", r"토목",
    r"feasibility stud", r"타당성조사", r"타당성 조사",
    r"due diligence", r"실사",
    r"detailed design", r"실시설계",
    r"construction supervision", r"시공감리", r"감리",
]

# 강한 포함 신호가 전혀 없을 때만 이 키워드로 제외 판단
EXCLUDE_PATTERNS = [
    r"\bAI\b", r"artificial intelligence", r"인공지능",
    r"software development", r"소프트웨어",
    r"\bIT\b system", r"digital platform",
    r"architectur", r"건축\s*설계", r"건물\s*설계",
    r"education curriculum", r"교육과정",
    r"\bhealth\b", r"hospital", r"보건", r"의료",
    r"vaccin",
    r"microfinance", r"banking sector", r"금융권",
    r"tourism", r"관광",
    r"gender action", r"양성평등",
    r"agricultur(e|al) value chain", r"농업 가치사슬",
]

_INCLUDE_RE = re.compile("|".join(INCLUDE_PATTERNS), re.IGNORECASE)
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


def is_relevant(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t)
    if not combined:
        return True  # 판단할 정보 자체가 없으면 일단 포함 (안전하게)
    if _INCLUDE_RE.search(combined):
        return True
    if _EXCLUDE_RE.search(combined):
        return False
    return True  # 애매하면 포함
