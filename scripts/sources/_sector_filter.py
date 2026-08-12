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
# 영어/한국어뿐 아니라, World Bank/AfDB 등에 자주 쓰이는 프랑스어/포르투갈어/스페인어도
# 함께 포함해야 원문이 그 언어인 공고도 정확히 분류할 수 있음 (번역은 안 하지만 키워드는 인식)
INCLUDE_PATTERNS = [
    r"irrigation", r"관개", r"irrigación", r"irrigação",
    r"\broad\b", r"highway", r"도로", r"\broute\b", r"routier", r"estrada", r"rodovia", r"carretera", r"vial\b",
    r"water resource", r"water supply", r"수자원", r"상수도", r"용수",
    r"ressources en eau", r"alimentation en eau", r"recursos h[íi]dricos", r"abastecimento de [áa]gua",
    r"\bdam\b", r"댐", r"barrage", r"barragem", r"presa\b",
    r"bridge", r"교량", r"\bpont\b", r"ponte\b", r"puente\b",
    r"drainage", r"배수", r"drenagem", r"drenaje",
    r"flood", r"홍수", r"inondation", r"inunda[çc][ãa]o", r"inundaci[óo]n",
    r"transport", r"교통", r"transporte",
    r"hydro", r"수력",
    r"canal", r"수로",
    r"sewer", r"하수", r"assainissement",
    r"embankment", r"제방",
    r"reservoir", r"저수지", r"r[ée]servoir",
    r"civil engineering", r"토목", r"g[ée]nie civil", r"engenharia civil", r"ingenier[íi]a civil",
    r"feasibility stud", r"타당성조사", r"타당성 조사",
    r"[ée]tude de faisabilit[ée]", r"estudo de viabilidade", r"estudio de factibilidad",
    r"due diligence", r"실사",
    r"detailed design", r"실시설계", r"conception d[ée]taill[ée]e", r"[ée]tudes d[ée]taill[ée]es",
    r"projeto detalhado", r"dise[ñn]o detallado",
    r"construction supervision", r"시공감리", r"감리",
    r"supervision des travaux", r"contr[ôo]le des travaux", r"supervis[ãa]o de obras", r"supervisi[óo]n de obras",
]

# 강한 포함 신호가 전혀 없을 때만 이 키워드로 제외 판단
EXCLUDE_PATTERNS = [
    r"\bAI\b", r"artificial intelligence", r"인공지능", r"intelligence artificielle", r"intelig[êe]ncia artificial",
    r"software development", r"소프트웨어",
    r"\bIT\b system", r"digital platform",
    r"architectur", r"건축\s*설계", r"건물\s*설계", r"architecture\b",
    r"education curriculum", r"교육과정", r"[ée]ducation\b", r"educa[çc][ãa]o\b", r"educaci[óo]n\b",
    # 청소년/여성 역량강화, 교육·사회개발 프로그램 (교육/사회분야 전반)
    r"adolescent", r"youth empowerment", r"girls[’']?\s*(initiative|education|empowerment)",
    r"women['’]?s empowerment", r"skills? training program", r"life skills",
    r"scholarship program", r"literacy program",
    r"\bhealth\b", r"hospital", r"보건", r"의료", r"sant[ée]\b", r"sa[úu]de\b", r"salud\b",
    r"vaccin",
    r"microfinance", r"banking sector", r"금융권",
    r"finance for jobs", r"jobs? and (economic|livelihood)", r"access to finance",
    r"financial inclusion", r"private sector development",
    # 탈탄소화/기후정책, 교사교육/스마트교육 등 산업정책·교육 분야 PMC(사업관리)용역
    # (PMC 자체는 다산도 할 수 있는 역할이지만, 관리 대상 사업이 무관 분야인 경우)
    r"탈탄소화", r"decarboniz", r"교사\s*교육", r"스마트\s*교육", r"학생\s*성장",
    # 홍보/대국민 인식제고 캠페인 컨설팅 (분야와 무관하게 캠페인/홍보 자체가 다산 업무 아님)
    r"public awareness campaign", r"awareness campaign", r"communication campaign",
    r"인식\s*제고\s*캠페인",
    r"tourism", r"관광", r"tourisme", r"turismo",
    r"gender action", r"양성평등", r"genre\b", r"g[êe]nero\b",
    r"agricultur(e|al) value chain", r"농업 가치사슬",
    r"livestock", r"축산", r"dairy", r"낙농", r"[ée]levage", r"b[ée]tail", r"laitier",
    r"agriculture moderniz", r"농업\s*현대화",
    r"voltage network", r"transmission line", r"transmission network",
    r"transmission infrastructure", r"power grid", r"substation",
    r"송전", r"배전", r"변전소", r"전력망",
    r"ligne de transmission", r"r[ée]seau [ée]lectrique", r"linha de transmiss[ãa]o", r"l[íi]nea de transmisi[óo]n",
    r"cybersecurity", r"cyber security", r"cybers[ée]curit[ée]", r"ciberseguridad",
    r"\bICT\b", r"information and communications technology",
    r"digital transformation", r"digital integration", r"e-government",
    r"digital\s+\w+\s+acceleration", r"digital economy", r"digital government",
    r"e-governance", r"smart government",
    r"computer emergency response", r"\bCERT\b",
    r"telecommunications sector", r"telecomunica[çc][õo]es", r"telecomunicaciones",
    r"data center", r"network security", r"information security",
    # 소액 물품/장비 구매용 조달 방식(견적요청). 컨설팅 용역(RFP/EOI)이 아니라
    # 쇼핑(shopping) 방식 소규모 조달이라 다산이 참여할 대상이 아님.
    # 분야(태양광 등)가 아니라 조달 방식 자체로 걸러내므로, 관련 분야 공고가
    # RFP/EOI 방식으로 나오면 이 키워드에 안 걸려 계속 포함됨.
    r"demande de cotation", r"request for quotation", r"\bRFQ\b",
    r"shopping method", r"solicitud de cotizaci[óo]n", r"pedido de cota[çc][ãa]o",
    # 회계/정산 등 행정 지원업무 선정 공고(설계·시공·감리 용역이 아님)
    r"위탁정산기관", r"정산기관 선정", r"회계법인 선정",
    # 행사운영대행(이벤트 에이전시)이나, 국내 정부부처의 공모사업 자체를
    # 운영·지원해주는 행정지원 용역 (실제 해외 프로젝트 설계/조사가 아님)
    r"행사\s*대행", r"행사\s*기획", r"공모\s*제안사업",
]

_INCLUDE_RE = re.compile("|".join(INCLUDE_PATTERNS), re.IGNORECASE)
_EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

# 개인 직책 채용(사업공고가 아니라 사람 한 명 뽑는 공고)을 걸러내기 위한 패턴.
# "M&E Officer", "HS Specialist", "Road Data Collection Specialist"처럼
# 제목이 짧고 직책명으로 끝나면 채용공고로 간주한다.
# (사업 키워드가 있어도 이건 무조건 제외 — "Road Data Collection Specialist"도 걸러야 함)
# 직책명 뒤에 "(PC)", "(TA)", "(M&E)." 같은 괄호 약어나 마침표가 붙어도
# "직책명으로 끝난다"고 인식하도록 허용 (예: "Project Coordinator (PC).")
_JOB_TITLE_ENDING_RE = re.compile(
    r"\b(specialist|officer|expert|coordinator|advisor|adviser|analyst|manager|"
    r"scientist|auditor|economist|consultant|controller|director|assistant|"
    r"associate|engineer|accountant|secretary|technician)s?\s*(\([A-Za-z&]{1,6}\))?[\s\.\)]*$",
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


def has_strong_relevance_signal(*texts: str) -> bool:
    """INCLUDE_PATTERNS(관개/도로/댐 등 핵심 인프라 키워드)에 확실히 걸리는지만
    판단한다. 위험국 필터처럼 "애매하면 포함" 원칙을 뒤집어야 하는 경우에 쓴다."""
    combined = " ".join(t for t in texts if t)
    if not combined:
        return False
    return bool(_INCLUDE_RE.search(combined))


# 자체적으로 출장이 어려운 위험국/분쟁국. 이 국가들은 "애매하면 포함" 원칙을
# 적용하지 않고, 관개/도로/댐 등 핵심 인프라 키워드가 확실히 있을 때만 포함한다
# (예: "도로 재건 사업"은 유지, "CERT 컨설팅"처럼 애매한 건 제외).
# 국가명은 World Bank(영문) / 국내 소스(국문) 양쪽 표기를 모두 등록해야 함.
# 남수단은 제외 대상에서 뺐음(사용자 확인) — "수단"의 부분 문자열이 아니라
# 정확히 일치하는 국가명만 매칭하므로 "남수단"/"South Sudan"은 걸리지 않음.
RISK_COUNTRIES_EN = {
    "somalia", "afghanistan", "yemen", "syria", "syrian arab republic",
    "libya", "sudan", "ukraine",
}
RISK_COUNTRIES_KR = {
    "소말리아", "아프가니스탄", "예멘", "시리아", "리비아", "수단", "우크라이나",
}


def is_risk_country(country: str) -> bool:
    if not country:
        return False
    c = country.strip()
    if c in RISK_COUNTRIES_KR:
        return True
    return c.lower() in RISK_COUNTRIES_EN
