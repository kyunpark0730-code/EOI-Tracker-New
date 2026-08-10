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
    r"voltage network", r"transmission line", r"transmission network",
    r"transmission infrastructure", r"power grid", r"substation",
    r"송전", r"배전", r"변전소", r"전력망",
]

_INCLUDE_RE = re.compile("|".join(INCLUDE_PATTERNS), re.IGNORECASE)
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

# 개인 직책 채용(사업공고가 아니라 사람 한 명 뽑는 공고)을 걸러내기 위한 패턴.
# "M&E Officer", "HS Specialist", "Road Data Collection Specialist"처럼
# 제목이 짧고 직책명으로 끝나면 채용공고로 간주한다.
# (사업 키워드가 있어도 이건 무조건 제외 — "Road Data Collection Specialist"도 걸러야 함)
_JOB_TITLE_ENDING_RE = re.compile(
    r"\b(specialist|officer|expert|coordinator|advisor|adviser|analyst|manager|"
    r"scientist|auditor|economist|consultant)s?\s*$",
    re.IGNORECASE,
)
# 아래 단어가 있으면 '한 명 채용'이 아니라 '용역/사업' 공고이므로 채용으로 간주하지 않음
_NOT_JOB_HINT_RE = re.compile(
    r"consultancy services|consulting services|request for proposal|invitation for bid|"
    r"expression of interest|firm|company|contractor|supplier|construction of|"
    r"rehabilitation of|upgrading of|supervision of|design and|feasibility",
    re.IGNORECASE,
)


def is_individual_job_posting(title: str) -> bool:
    """개인 직책(채용) 공고인지 판단. 짧고 직책명으로 끝나며, 사업/용역을 나타내는
    문구가 없으면 채용공고로 판단한다."""
    if not title:
        return False
    title = title.strip()
    word_count = len(title.split())
    if word_count > 8:
        return False  # 보통 채용공고 제목은 짧음
    if _NOT_JOB_HINT_RE.search(title):
        return False  # 사업/용역 성격 문구가 있으면 채용공고가 아님
    return bool(_JOB_TITLE_ENDING_RE.search(title))


def is_relevant(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t)
    if not combined:
        return True  # 판단할 정보 자체가 없으면 일단 포함 (안전하게)
    if _INCLUDE_RE.search(combined):
        return True
    if _EXCLUDE_RE.search(combined):
        return False
    return True  # 애매하면 포함
