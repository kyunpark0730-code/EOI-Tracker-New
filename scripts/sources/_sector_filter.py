# -*- coding: utf-8 -*-
"""
다산컨설턴트의 핵심 관심 분야(관개, 도로, 수자원 등 토목 인프라)와 확실히 무관한
공고를 걸러내는 공통 필터.

원칙: "애매하면 살린다." 관련 키워드가 하나라도 있으면 무조건 포함시키고,
관련 키워드가 전혀 없고 명백히 무관한 키워드(AI, 건축설계, 보건, 교육 등)만
있는 경우에만 제외한다. 판단이 애매한(둘 다 없는) 경우는 기본적으로 포함한다.
"""

import re

# ["하드 제외"] 이 표현들은 "관개/도로" 같은 핵심 인프라 키워드가 같이 있어도
# 무조건 제외한다 — 인프라 사업 산하 공고라도, 실제 업무 자체가 다산의 전문영역
# (설계/조사/감리)과 명백히 다른 별도 전문분야이기 때문. 아래 EXCLUDE_PATTERNS는
# INCLUDE가 있으면 밀리지만, 이 목록은 INCLUDE보다 먼저 검사해서 항상 이긴다.
# (실제로 "Road" 등 INCLUDE 키워드와 같이 나와서 놓쳤던 사례들 — ITS 타당성조사,
# 축산 창고 감리, RAP 이주대책계획 — 을 계기로 만듦)
HARD_EXCLUDE_PATTERNS = [
    r"resettlement action plan", r"\bRAP\b", r"이주대책계획",
    r"land acquisition and resettlement", r"social safeguards", r"involuntary resettlement",
    # 프랑스어권 RAP(이주대책계획) — 프랑스어 약어는 "PAR"이지만 "par"는 불어에서
    # "~에 의해"라는 뜻으로 매우 흔한 단어라 \bPAR\b 자체는 쓰지 않고, 반드시 전체
    # 문구로만 매칭한다. 이주대책계획(RAP)은 기존 영어 패턴과 마찬가지로 설계/감리
    # 등 INCLUDE 키워드와 같이 나와도 무조건 제외 — RAP 자체가 별도 사회안전장치
    # 전문영역이기 때문 (카메룬/콩고 전력망 건설사업 순수 이주대책 용역 사례).
    r"plan d[’']?action de r[ée]installation", r"r[ée]installation involontaire",
    # 원주민계획(Indigenous Peoples Plan, PPA) — RAP과 같은 세계은행 사회안전장치
    # 문서 종류. 콩고민주공화국 PDTC 도로포장 사업의 "Plan en faveur des Populations
    # Autochtones" 사례. "route"/도로 등 INCLUDE 키워드와 같이 나와도 RAP과 같은
    # 이유로 무조건 제외 — 설계/감리가 아니라 사회안전장치 전문영역이기 때문.
    r"plan (en faveur des |des )?(populations|peuples) autochtones",
    r"indigenous peoples plan",
    r"livestock", r"축산", r"dairy", r"낙농", r"[ée]levage", r"b[ée]tail", r"laitier",
    r"intelligent transport system", r"지능형\s*교통체계",
    # 소프트웨어 개발자/IT 인력 파견(아웃소싱), 인일(jours-homme) 단위 IT 상주지원.
    # 프로젝트명이 뭐든(디지털화/전자정부 등) 업무 자체가 개발 인력 파견이면 무조건 제외.
    r"d[ée]veloppeur", r"software developer", r"ux/ui", r"devops",
    # 산림복원/바이오경제/기후스마트농업 프로그램의 PMO/PMC 등 사업관리 용역
    # (PMO/PMC 역할 자체는 다산도 하지만, 관리대상 사업이 산림·생물다양성 분야면 무관)
    r"bioeconomy", r"forest restoration", r"climate-smart agriculture",
    r"reflorestamento", r"agroforest",
    # 마을 단위 토지이용계획/생태 회랑 등 GEF류 환경보전·토지이용 프로그램.
    # 수자원/관개 관리 사업 산하 세부 과업으로 붙는 경우가 있어 INCLUDE와
    # 겹칠 수 있으므로 하드제외로 분류.
    r"village land use", r"land use action plan", r"biodiversity corridor",
    r"community-based natural resource management",
    # 생물다양성 조사·생태복원계획 (르완다 Nyungwe-Ruhango 사례) — 위와 같은 이유로
    # 환경보전·생태 분야라 다산 전문영역(토목 설계/감리)과 무관
    r"biodiversity baseline survey", r"ecological restoration plan",
    r"ecosystem-based restoration",
    # 생계형 소규모 사업(livelihood subproject) 사업계획서 작성 등 소득창출·
    # 가치사슬 경제개발 자문 (엔지니어링이 아니라 비즈니스 컨설팅 성격)
    r"livelihood subproject", r"business plans? for livelihood", r"value chains? for",
    # 공공건물/재난대피소 신축·보강·재건축 설계 및 감리 (도로/관개/댐/제방 등
    # 토목이 아니라 건축(building) 분야라 construction supervision 등 INCLUDE
    # 키워드와 겹쳐도 하드제외)
    r"public buildings?", r"emergency shelters?", r"retrofitting of (public )?buildings?",
    # 나라장터 수집기가 수요기관명에 "해외" 포함 여부로 필터링하는데, "김해외국어고등학교"처럼
    # 지명·교명에 우연히 "해외" 두 글자가 끼어 들어오는 학교/교육청 공고를 걸러냄
    # (국외 현장체험학습 등 학생 해외연수 용역 - 해외 인프라 사업과 무관)
    r"고등학교", r"교육청", r"현장체험학습",
    # 계량과학(metrology) 계측장비 운영 역량강화 교육훈련 (계측표준 전문분야,
    # 산업경쟁력 프로젝트 산하로 나와도 다산 엔지니어링 전문영역과 무관)
    r"metrology equipment", r"metrology institute", r"calibration and measurement capabilit",
    # 법률/사법 분야 교육·역량강화 (판사·행정관 연수, 파산법 등 법조인 대상 훈련)
    r"insolvency", r"judges? and administrators", r"judicial training",
    r"commercial law", r"legal training program",
    # 해안지구 도시재생/공공공간 개선(공원·보행로·녹지 등) — 관개/도로/수자원처럼
    # 물리적 토목이 아니라 도시계획·공공공간 조성 성격이라 다산 전문영역과 다름
    r"eco-inclusive district", r"distrito eco-inclusivo", r"public space improvement",
    r"mejoramiento de espacios p[úu]blicos", r"coastal resilience", r"franja costera",
    # 도시개발 마스터플랜/공간계획 수립, 도시 시뮬레이션·계획 플랫폼 구축 -
    # 물리적 토목이 아니라 도시계획·정책 수립 자체가 산출물인 용역
    r"urban development masterplan", r"spatial development framework",
    r"urban scenario planning platform", r"spatial planning", r"spatial plan\b",
    r"urban spatial plan",    # 전력시장 설계·거래제도 자문 (물리적 송배전망 설계가 아니라 시장운영/규제 정책)
    r"trading bilateral contract market", r"electricity market design",
    r"power market reform", r"market operator",
    # 위와 같은 성격(전력시장/거래 자문)의 스페인어 표현 — 볼리비아 "Estudio de Mercado
    # para intercambios Internacionales" 사례(전력 국제거래 시장연구, 물리적 설비가
    # 아니라 시장·정책 자문이라 다산 전문영역과 무관)
    r"estudio de mercado para intercambios internacionales", r"mercado el[ée]ctrico",
    # 에너지효율 등급라벨링 제도/규정 마련 (볼리비아 IDTR III 라벨링 프로그램 사례) —
    # 물리적 설비 설계가 아니라 라벨링 표준·규정 수립 정책자문이라 다산 전문영역과 무관
    r"etiquetado de eficiencia energ[ée]tica", r"energy efficiency label(l)?ing",
    r"programa de etiquetado",
    # 디젤 사용량 분석 및 청정에너지 대체(에너지효율 진단) 연구 (볼리비아 IDTR III
    # 광산지역 디젤대체 사례) — 물리적 설비 설계가 아니라 에너지효율 진단/정책 자문
    r"sustituci[óo]n de diesel", r"diesel substitution",
    r"jours-homme", r"person-days? of it", r"it staffing",
    r"탈탄소화", r"decarboniz",
    # 탄소배출권 크레딧 개발/등록/판매(monetization), MRV(모니터링·검증) 등
    # 탄소금융 자문. 대중교통(BRT) 등 인프라 사업 산하 공고라 INCLUDE(transport 등)에
    # 걸려도, 실제 업무는 탄소시장/GHG 회계 전문분야라 다산 전문영역과 다름.
    r"carbon credit", r"carbon crediting", r"carbon monetization", r"carbon monetisation",
    r"carbon market", r"ghg accounting", r"\bmrv\b", r"verra\b", r"gold standard\b",
    r"\bcdm\b", r"article 6\.4",
    # 탄소가격제(탄소세/부과금) 설계·요율 산정 — 기니 광업부문 탄소가격제(ITC) 파일럿
    # 사례. "extractif"/"minier" 등 산업 맥락이라 INCLUDE 키워드 자체는 없지만,
    # 위 탄소시장(carbon market)과 마찬가지로 탄소경제·기후정책 전문분야라 다산
    # 전문영역(토목 설계/조사/감리)과 무관.
    r"tarification du carbone", r"carbon pricing", r"redevance carbone", r"carbon levy",
    r"courbe de co[ûu]t marginal d[’']?abattement", r"marginal abatement cost curve",
    # REDD+/산림탄소 모니터링(MNV=MRV의 프랑스어 표현) — 기니 REDD+ 국가 MNV체계
    # 강화 사례. 산림 원격탐사·산림재고조사(IFN)·탄소회계(AFOLU/LULUCF) 등 산림탄소
    # 전문분야라 다산 전문영역(토목 설계/조사/감리)과 무관.
    r"\bMNV\b", r"REDD\+", r"forest monitoring", r"national forest monitoring",
    r"surveillance des for[êe]ts", r"inventaire forestier national", r"\bIFN\b",
    r"afolu", r"\blulucf\b",
    # 발전/에너지 사업 시행기관 자체에 대한 경영·제도 자문(조직개편/인사/재무/요금·규제/
    # ERP 등). "Hydropower" 등 INCLUDE 키워드에 걸려도, 실제 업무는 엔지니어링
    # (설계/타당성조사/감리)이 아니라 기관 경영컨설팅이라 다산 전문영역과 다름.
    r"human capital blueprint", r"human capital development plan",
    r"\bassessment center\b", r"\bchange management\b",
    r"\bhc\b management practices",
    # 연구기관 자체의 역량강화(조직·인력·제도 강화) 사업 — 파키스탄 PCRWR(물연구
    # 위원회) "연구 인프라 개선 및 통합수자원관리 역량강화 PMC" 사례. "수자원" 등
    # INCLUDE 키워드가 있어도, 실제 업무가 연구기관의 조직·역량 강화(institutional
    # strengthening과 같은 성격)면 관개/댐 등 물리적 설계·시공감리가 아니므로 다산
    # 전문영역과 무관 (사용자 확인, 2026-08).
    r"연구기관\s*역량\s*강화", r"연구소\s*역량\s*강화", r"연구\s*인프라\s*개선",
    r"research institute.*capacity", r"research council.*capacity", r"\bPCRWR\b",
    # 농업협동조합 등을 위한 공동 농기계 파크 설립 지원(제도·재정·법률·운영모델
    # 수립, 역량강화 등) — 튀르키예 TARDP "Ortak Makine Parkları" 사례. 지진 피해
    # 농업 프로젝트 산하 공고라도, 실제 업무는 농기계 공동이용 조직의 사업모델·
    # 운영체계·역량강화 컨설팅이라 토목 설계/시공감리와 무관.
    r"machinery park", r"ortak makine park", r"agricultural cooperative",
    r"farmer(s)?['’]? cooperative",
    # 상하수도 등 인프라 운영기관의 "자산관리체계(Gestion Patrimoniale)" 구축 -
    # 물리적 설계/시공이 아니라 자산대장(référentiel patrimonial)·GIS·전산유지보수
    # 관리시스템(GMAO)·절차매뉴얼 등 제도·정보시스템 자문(콩고 Congolaise des Eaux
    # 사례). "water supply" 등 INCLUDE 키워드와 함께 나올 수 있어 하드제외로 분류.
    r"gestion patrimoniale", r"gestion du patrimoine", r"r[ée]f[ée]rentiel patrimonial",
    r"asset management system",  r"\bGMAO\b",
    # 전사적 리스크관리(ERM)/내부통제 시스템 구축 (우즈베키스탄 철도공사 사례) —
    # "Transport" 등 INCLUDE 키워드에 걸려도, 실제 업무는 COSO/ISO 31000 기반
    # 리스크관리·내부통제 컨설팅이라 기관 경영자문 성격, 엔지니어링과 무관.
    r"enterprise risk management", r"\bERM\b system", r"\bCOSO\b", r"iso ?31000",
    # 항만/물류 시설(컨테이너터미널 등) - "transport" INCLUDE 키워드에 걸릴 수 있지만
    # 다산은 항만·물류 분야를 하지 않으므로 하드제외
    r"container terminal", r"ports and logistics", r"port authority",
    r"\bseaport\b", r"maritime terminal",
    r"orpaillage", r"artisanal (small-scale )?mining",
    r"mine (site )?(reclamation|rehabilitation|closure)",
    r"restoration (of |des )?(mining|mine) sites?", r"sites? d[’']?orpaillage",
    r"tourism", r"관광", r"tourisme", r"turismo", r"touristique",
    # 수산업/어업 관리·법제 자문 및 어항(fisheries harbour) 설계·감리 — "detailed design",
    # "construction supervision" 등 INCLUDE 키워드가 같이 있어도(스리랑카 어항 설계·감리
    # 사례), 항만/물류와 같은 이유로 다산 전문영역과 무관하므로 하드제외로 분류.
    r"fisheries", r"어업", r"수산업", r"p[êe]cheries?", r"pesca\b", r"pesquer[íi]a",
    r"fish landing",
    # 양식업(부화장 등) — 코트디부아르 alevinage(치어부화장) 관리체계 수립 사례.
    # 어업과 마찬가지로 다산 전문영역과 무관 (토목이 아니라 수산양식/기관 거버넌스)
    r"alevinage", r"pisciculture", r"aquaculture", r"station(s)? aquacole",
    # 고형폐기물 관리 정책/제도 진단 (필리핀 Clean Metro Manila 사례) - 시설 설계가
    # 아니라 수거·처리 체계의 정책·거버넌스·재정 진단 자문이라 다산 전문영역과 무관.
    # 폐기물 관리 자체도 다산이 하는 분야가 아님(항만/수산업과 같은 이유).
    r"solid waste mangement", r"waste management sector",
    # 에너지저장장치(BESS) — "타당성조사" 등 INCLUDE 키워드와 같이 나오는 경우가
    # 있어 하드제외로 이동 (전력망/변전소와 같은 전력 부문, 다산 전문영역 아님)
    r"\bBESS\b", r"battery energy storage", r"에너지저장장치",
    # 송배전망(전력망) 시설 관련 전 분야 — 사용자 확인(2026-08): 전력 송전/배전망은
    # "Construction supervision"/"Design" 등 INCLUDE 키워드가 같이 나와도(에티오피아
    # 배전망 안정화 사업의 시공감리 사례) 다산이 검토하는 분야가 아니므로 하드제외로
    # 분류한다. 기존에는 소프트제외였으나 감리 키워드에 밀려 포함되는 문제가 있었음.
    r"voltage network", r"transmission line", r"transmission network",
    r"transmission infrastructure", r"transmission grid", r"power grid", r"substation",
    r"distribution network", r"distribution grid", r"distribution line",
    r"송전", r"배전", r"변전소", r"전력망",
    r"ligne de transmission", r"r[ée]seau [ée]lectrique", r"linha de transmiss[ãa]o", r"l[íi]nea de transmisi[óo]n",
    # 송전선 공사(EIB 사례) — "transmission"이라는 단어 없이 "400 kV ... double-circuit
    # line"처럼 전압(kV) 수치와 "line"/"circuit"만으로 표현되는 경우가 있어, 위의
    # "transmission line" 등 문구 매칭에 걸리지 않고 새어나갔다(모로코 Chemaia-Tensift
    # 400kV 송전선 사례). 전압(kV) 수치가 있으면 거의 항상 전력 계통 설비이므로,
    # 숫자+kV 표기 자체를 하드제외 지표로 추가한다.
    r"\d+\s*kv\b", r"circuit line", r"power line",
    # 정보화사업 감리(IT/소프트웨어 프로젝트 관리·감독) — "감리"라는 단어가
    # 건설감리와 똑같이 쓰이지만 실제로는 IT사업으로 완전히 다른 분야
    # "정보시스템" 자체가 이미 IT 분야 지표라, "정보화 감리"라는 정확한 문구가
    # 아니라 "정보시스템 개선 사업 감리"처럼 다르게 풀어써도 걸리도록 별도로 추가
    # (우즈베키스탄 지식재산권 정보시스템 감리 사례 — INCLUDE의 "감리"에 밀려
    # 잘못 포함됐었음).
    r"정보화\s*감리", r"정보화\s*사업\s*관리", r"정보시스템",
    r"information management (system|platform)",
    r"sector information management",
    # 생성형 AI 등 IT 서비스 구축 사업 감리 — "감리"가 있어도 정보시스템처럼
    # IT/디지털 분야이지 토목(관개/도로/댐) 감리가 아니므로 무관(한국해외인프라
    # 도시개발지원공사 "대내 생성형 AI 서비스 구축 사업 감리" 사례).
    r"생성형\s*AI", r"AI\s*서비스\s*구축",
    # 국내 산업협회(해외건설협회 등)의 시장동향/진출환경 조사·리포트 — 특정 사업의
    # 설계/감리가 아니라 업계 전반의 시장조사·리서치 용역이라 다산 전문영역과 무관
    r"진출환경", r"시장동향\s*조사", r"업계\s*동향\s*조사",
    r"우수사례집\s*발간", r"사례집\s*발간",
    # 석유/원유 저장시설(탱크팜) 건설·확장 — 관개/댐 등과 무관한 석유화학·에너지
    # 저장 인프라 분야라 다산 전문영역과 무관 (오만 두큼 라스 마르카즈 원유저장소 사례)
    r"원유\s*저장", r"저유소", r"oil storage", r"petroleum storage", r"crude oil storage",
    r"tank farm",
    # KOICA 등 국내 행정지원 용역(임금체계/전시관 시설/사업평가 등 -
    # 해외 인프라 설계·감리가 아니라 기관 내부 행정·평가 업무)
    r"임금체계", r"전시관", r"심층평가", r"배움터",
    # 사업/프로그램 성과평가(M&E) 컨설팅 — 케냐 KISIP2 "End of Program Evaluation" 사례.
    # 설계·감리가 아니라 사업 종료 후 성과·수혜자 평가 자문이라 다산 전문영역과 무관
    # (관개/도로 등 인프라 사업 산하 공고라도 이 업무 자체가 평가·컨설팅이면 제외).
    r"end of program evaluation", r"beneficiary assessment",
    r"value for money assessment", r"impact evaluation",
    r"independent verification agent", r"performance-based grants?",
    r"results verification", r"independent verification of results",
    r"verification of results",
    # 거버넌스/반부패 진단조사(설문조사 분석 등 통치체계 자문) — 아이티 ULCC
    # "enquête diagnostique sur la gouvernance et la corruption" 사례. 설계·감리가
    # 아니라 통치구조·반부패 진단·평가 자문이라 다산 전문영역과 무관.
    r"governance and corruption diagnostic", r"diagnostic survey on governance",
    r"enqu[êe]te diagnostique sur la gouvernance", r"gouvernance et (la )?corruption",
    # 세금/부가가치세(VAT) 인지도·이행준비도 설문조사(Baseline/Midline/Endline) —
    # 라이베리아 GREAT 프로젝트 "VAT Awareness and Readiness Surveys" 사례. 설계·감리가
    # 아니라 납세자 인지도 조사·홍보라 다산 전문영역과 무관.
    r"vat awareness", r"tax awareness (and readiness)?",
    r"awareness and readiness surveys?",
    # 사회·경제 프로그램의 기초선(Baseline) 설문조사 단독 용역 — 타지키스탄
    # "Women's Economic Empowerment Project" "Baseline Survey" 사례. 설계·감리가
    # 아니라 사업 시작 전 현황조사(설문)만 단독으로 발주된 M&E 성격 용역이라
    # 다산 전문영역과 무관 (환경/생물다양성 기초조사는 이미 별도 패턴으로 처리됨).
    r"\bbaseline survey\b",
    # 재무제표 감사(외부회계감사) 용역 - 관개/도로 등 인프라 사업 산하 공고라 INCLUDE에
    # 걸려도, 실제 업무는 회계·재무감사 전문용역(공인회계사)이라 다산 전문영역과 다름
    r"external auditor", r"financial audit", r"audit comptable et financier",
    r"auditeur externe", r"audit financier", r"audit des comptes",
    r"firme d[\'’]?audit", r"cabinet d[\'’]?audit",
    # 재무제표 작성/정정(회계자문) — 기니 EDG(전력공사) "Consultant Financier"
    # 재무제표 작성 및 준비금(reserves) 오류 정정 자문 사례. 외부회계감사와
    # 마찬가지로 엔지니어링이 아니라 회계·재무 전문영역이라 다산 전문영역과 무관.
    r"[ée]laboration des [ée]tats financiers", r"correction des r[ée]serves",
    r"consultant financier",
    # EIB/EIB그룹 등 발주기관 자체의 사내 운영 조달(IT/보험/채용/급여/컨설팅 등
    # 행내 서비스 계약) — 회원국 인프라 개발사업이 아니라 발주기관 조직 내부
    # 운영을 위한 조달이라 다산 전문영역과 무관
    r"for the eib group", r"eib groups?", r"\bIT\s+security\b",
    # 물품/장비 납품 계약(Goods) — World Bank는 procurement_group(GO)으로 구조적으로
    # 걸러내지만 EIB 등 다른 소스는 이 필드가 없어서, "장비 납품/공급" 자체를 뜻하는
    # 표현으로 대신 걸러낸다. 컨설팅 용역이 아니라 물품 조달이라 다산 전문영역과 무관.
    r"fourniture d[’']?[ée]quipements", r"fourniture de biens",
    r"fourniture et (pose|installation)", r"supply of equipment",
    r"supply and delivery of equipment", r"procurement of goods",
    # 시공 계약 자체(Works) — 마찬가지로 EIB 등에는 WB의 CW 같은 구조적 필드가 없어서
    # 표현으로 대신 걸러낸다. "Empreitada"(포르투갈어 시공계약), "감리/발주감독"이 아니라
    # 시공사가 직접 입찰하는 계약이라 다산(설계·감리 컨설턴트) 전문영역과 무관.
    r"\bempreitada\b", r"march[ée] de travaux", r"ex[ée]cution des travaux",
    r"obras? de construcci[óo]n", r"ejecuci[óo]n de obras",
    # 학교/유치원 등 건축(architecture) 분야 건물 신축·보강·재건축 설계 및 감리
    # (관개/도로/댐 등 토목이 아니라 건축 분야라 기존 public buildings 하드제외와 같은 이유)
    r"kindergarten", r"[ée]cole maternelle", r"jardin d[’']?enfants",
    r"jardim de inf[âa]ncia", r"guarder[íi]a infantil",
    # 실험실/연구소 등 특수 건물(laboratory building) 신축 설계·감리 — 가이아나
    # One Health "국립 공중보건연구소(NPHRL) 건물" 사례. "detailed design"/
    # "construction supervision" 등 INCLUDE 키워드가 있어도, 학교/유치원과 같은
    # 이유로 토목(관개/도로/댐)이 아니라 건축(특수 실험시설) 분야라 다산 전문영역과
    # 무관.
    r"reference laboratory", r"laboratory building",
    # 위와 같은 실험실/연구소 건물의 프랑스어 표현 — 니제르 PISEN 사업 "Laboratoire
    # National de Qualité de l'Eau"(국립 수질검사연구소) 신축 설계(APS/APD)·시공감리
    # 사례. "études techniques"/"suivi contrôle des travaux" 등 INCLUDE 키워드가
    # 있어도 마찬가지로 건축 분야라 무관. "laboratoire" 단독은 시공 중 자재시험실처럼
    # 다산이 실제로 다루는 문맥에도 나올 수 있어 너무 넓으므로, "national"이 붙거나
    # 건물 자체를 가리키는 구체적인 표현으로만 좁혀서 잡는다.
    r"laboratoire national", r"b[âa]timent (du |de )?laboratoire",
    r"laboratoire de qualit[ée] de l[’']?eau",
    # 보건부(보건안보 프로그램) 산하 발주 공고 — 기니 PReSeS-AOC(서아프리카 보건안보
    # 프로그램) "bureau d'études d'ingénierie civile... infrastructures" 사례.
    # bid_description 자체는 "études techniques"/"suivi-contrôle"/"supervision des
    # travaux" 등 INCLUDE 키워드가 있어도, 발주기관이 보건부/보건안보 프로그램이면
    # (병원·보건소 등 보건 인프라가 실제 대상일 가능성이 높아) 다산 전문영역
    # (관개/도로/댐)과 무관한 것으로 간주한다. 기존 soft EXCLUDE의 "health"/"santé"는
    # ESIA/ESMP 보고서에 흔히 나오는 "public health and safety" 같은 일반적 문구까지
    # 걸릴 수 있어 hard exclude로 승격하지 않고, 발주기관 자체를 가리키는 좁은 표현만
    # hard exclude로 잡는다.
    r"minist[èe]re de la sant[ée]", r"ministry of health",
    r"health security (program|programme)", r"s[ée]curit[ée] sanitaire",
    # 기관 거버넌스/재무구조 설계 등 제도·경영 자문 (엔지니어링이 아니라 institutional
    # strengthening/management support consultant와 같은 성격의 자문)
    r"governance and financing model",
    # 타당성조사와 결합된 PPP 거래자문(Transaction Advisory) — 케냐 Horn of Africa
    # Gateway Development Project "나이로비-몸바사 도로 타당성조사 + PPP 거래자문"
    # 사례. "feasibility study"/"road" 등 INCLUDE 키워드가 있어도, 사업자 선정을
    # 위한 프로젝트 구조화·재무분석·조달지원 등 PPP 거래자문 역량을 필수로 요구하는
    # 결합형 용역이라 다산이 실제로 참여하지 않기로 한 유형.
    r"transaction advisory",
    # 도시 인프라 재원조달 방안 수립(신용등급 분석·재무모델) — 인도네시아 SCIP
    # "지속가능 재원조달 대안 선정 계산모델(CMSF)" 사례. 자격요건에 "water supply"
    # 등 INCLUDE 키워드가 있어도(용역 회사의 배경지식 요건일 뿐), 실제 과업은
    # shadow credit rating·financial model·financing scheme 선정 같은 순수 재무/
    # 금융자문이라 다산 전문영역(설계/시공감리)과 무관.
    r"shadow credit rating", r"financing scheme selection",
    r"sustainable financing alternatives", r"indicative financing schemes? selection",
    # 농촌금융/소액금융(microfinance) 개발 프로그램(EIB RUFIP III - 에티오피아 사례) —
    # 관개/도로 등 인프라의 설계·감리가 아니라 농촌 금융기관/신용 접근성을 개선하는
    # 금융부문 개발사업이라 다산 전문영역과 무관.
    r"rural finance", r"microfinance", r"micro-finance", r"financial inclusion",
    # 국가 에너지부문 투자프로그램/정책전략 수립 (마샬제도 REGAIN ESIP 사례) — 진단·
    # 최소비용개발경로·통합자원계획(IRRP)·재원조달전략·정책로드맵 등 국가 정책·전략
    # 수립이 중심이라, 개별 사업의 설계/감리/타당성조사가 아니라 다산 전문영역과 무관.
    r"energy sector investment program(me)?", r"sector investment programme",
    r"integrated resource and resilience plan", r"\bIRRP\b", r"least-cost development pathway",
    # 국가 단위 도로망 분류체계/우선순위 전략 재정립 — 콩고민주공화국 PDTC 사업
    # "classification routière" 재정립 연구 사례. 거시경제 분석·교통부문 진단·
    # 빈곤퇴치 국가전략 연계·투자프로그램 식별이 중심인 국가 정책·방법론 수립이라,
    # 자격요건에 "도로 타당성조사" 경력을 요구해도 실제 과업은 개별 도로 프로젝트의
    # 설계/타당성조사가 아니라 위 REGAIN ESIP(에너지정책)과 같은 성격의 국가전략
    # 수립이라 다산 전문영역과 무관.
    r"classification routi[èe]re", r"road classification (study|strategy|framework)",
    r"road network hierarchi[sz]ation",
    # 부품/장비 구매(물품 조달)의 전형적 표현 — 제목에 "(9 pcs.)"처럼 수량이 붙는 경우.
    # 프랑스어(fourniture)뿐 아니라 영어로도 이런 형태로 자주 나와서 별도로 잡는다.
    r"\(\s*\d+\s*pcs\.?\s*\)", r"\(\s*\d+\s*units?\s*\)",
    # EIB 등 발주기관 자체 직원 교육훈련(내부조달) — 기존 "formation du personnel"의
    # 영어 표현. 인프라 사업이 아니라 발주기관 내부 인사·역량강화 조달이라 무관.
    r"corporate (skills )?training", r"staff training",
    r"programa de capacita[çc][ãa]o", r"capacita[çc][ãa]o in company",
    r"compras p[úu]blicas",
    # 도시재생/친수구역 정비 등 공공공간 조성 사업 — "eco-inclusive district"와 같은
    # 성격(물리적 토목이 아니라 도시계획·공공공간 조성)의 영어 표현
    r"urban redevelopment", r"river-?front redevelopment", r"waterfront redevelopment",
]

# 하나라도 걸리면 무조건 포함 (토목/인프라 핵심 분야)
# 영어/한국어뿐 아니라, World Bank/AfDB 등에 자주 쓰이는 프랑스어/포르투갈어/스페인어도
# 함께 포함해야 원문이 그 언어인 공고도 정확히 분류할 수 있음 (번역은 안 하지만 키워드는 인식)
INCLUDE_PATTERNS = [
    r"irrigation", r"관개", r"irrigación", r"irrigação",
    r"\briego\b", r"sistema de riego",
    r"\broad\b", r"highway", r"도로",
    # 프랑스어 "route"(도로)는 "feuille de route"(로드맵), "en route"(진행 중)처럼
    # 도로와 무관한 관용구에도 흔히 쓰여서, 그 두 관용구 뒤에 오는 경우는 제외하고
    # 매칭한다 (부룬디 PAFEN e-GP 변화관리 사례 — "feuille de route e-GP"에 잘못
    # 걸려서 IT/변화관리 용역이 포함됐었음).
    r"(?<!feuille de )(?<!en )\broute\b",
    r"routier", r"estrada", r"rodovia", r"carretera", r"vial\b",
    r"water resource", r"water supply", r"수자원", r"상수도", r"용수",
    r"ressources en eau", r"alimentation en eau", r"recursos h[íi]dricos", r"abastecimento de [áa]gua",
    r"\bdam\b", r"댐", r"barrage", r"barragem", r"\bpresa\b",
    r"bridge", r"교량", r"\bpont\b", r"ponte\b", r"puente\b",
    r"drainage", r"배수", r"drenagem", r"drenaje",
    r"flood", r"홍수", r"inondation", r"inunda[çc][ãa]o", r"inundaci[óo]n",
    r"transport", r"교통", r"transporte",
    r"hydro", r"수력",
    # 포르투갈어/스페인어 "canal"은 수로라는 뜻 외에 "채널"(방송/소통 채널)이라는
    # 뜻으로도 흔히 쓰여서 — 특히 "multicanal"(다채널)처럼 다른 단어에 붙어있으면
    # 단어 경계가 없어 아무데나 걸릴 위험이 있다 (앙골라 AYEOP 커뮤니케이션 전략
    # 수립 용역 사례 — "multicanal"에 잘못 걸려서 포함됐었음). 최소한 단어 경계는
    # 지키도록 고친다.
    r"\bcanal\b", r"수로",
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
    r"fiscalizaci[óo]n de obras",
]

# 강한 포함 신호가 전혀 없을 때만 이 키워드로 제외 판단
EXCLUDE_PATTERNS = [
    r"\bAI\b", r"artificial intelligence", r"인공지능", r"intelligence artificielle", r"intelig[êe]ncia artificial",
    r"software development", r"소프트웨어",
    r"\bIT\b system", r"digital platform",
    # 문서보관/기록물 디지털화 진단·전략수립 용역 — 브라질 Progestão Alagoas
    # "diagnóstico arquivístico... digitalização dos registros funcionais" 사례.
    # 설계·감리가 아니라 행정기록물 관리·디지털화 자문이라 다산 전문영역과 무관.
    r"diagn[óo]stico arquiv[íi]stico", r"digitaliza[çc][ãa]o (dos |de )?registros",
    r"massa documental",
    # "digital platform"의 스페인어 표현 — 콜롬비아 Fondo Acción PMI "Interoperabilidad"
    # (시장정보 디지털 플랫폼 상호운용성) 사례. INCLUDE 키워드가 전혀 없는 순수 IT
    # 컨설팅이라 애매하면 포함 원칙에 걸려 잘못 포함됐었음.
    r"plataformas? digitales?", r"sistemas? de informaci[óo]n", r"interoperabilidad",
    r"architectur", r"건축\s*설계", r"건물\s*설계", r"architecture\b",
    r"education curriculum", r"교육과정", r"[ée]ducation\b", r"educa[çc][ãa]o\b", r"educaci[óo]n\b",
    # "education"이라는 단어 없이 "Lower-Secondary Curriculum" 식으로만 나오는 경우도
    # 있어서(그레나다/도미니카 사례) curriculum 자체를 별도로 잡는다
    r"\bcurriculum\b",
    # 청소년/여성 역량강화, 교육·사회개발 프로그램 (교육/사회분야 전반)
    r"adolescent", r"youth empowerment", r"youth opportunit", r"girls[’']?\s*(initiative|education|empowerment)",
    r"women['’]?s empowerment", r"skills? training program", r"business development services",
    r"life skills", r"scholarship program", r"literacy program",
    r"\bhealth\b", r"hospital", r"보건", r"의료", r"sant[ée]\b", r"sa[úu]de\b", r"salud\b",
    r"vaccin",
    r"microfinance", r"banking sector", r"금융권",
    r"financial sector", r"banking (and|&) finance institute", r"central bank",
    r"finance for jobs", r"jobs? and (economic|livelihood)", r"access to finance",
    r"financial inclusion", r"private sector development",
    r"investment facilitation", r"investor engagement", r"investment package",
    r"project teaser",
    # 위 "business development services"/"private sector development"(중소기업
    # 역량강화·일자리창출)의 스페인어 표현 — 엘살바도르 BANDESAL "MIPYME(중소기업)
    # 역량강화를 통한 일자리창출 기회 진단" 사례. 토목(관개/도로/댐)이 아니라
    # 중소기업 지원/고용정책 분야라 다산 전문영역과 무관.
    r"creaci[óo]n de empleo", r"capacidades empresariales", r"\bmipyme\b",
    r"v[íi]nculos comprador[\s\-–]proveedor", r"fortalecimiento empresarial",
    # 탈탄소화/기후정책, 교사교육/스마트교육 등 산업정책·교육 분야 PMC(사업관리)용역
    # (PMC 자체는 다산도 할 수 있는 역할이지만, 관리 대상 사업이 무관 분야인 경우)
    r"교사\s*교육", r"스마트\s*교육", r"학생\s*성장",
    # 홍보/대국민 인식제고 캠페인 컨설팅 (분야와 무관하게 캠페인/홍보 자체가 다산 업무 아님)
    r"public awareness campaign", r"awareness campaign", r"communication campaign",
    r"인식\s*제고\s*캠페인",
    r"comunica[çc][ãa]o institucional",
    r"event management", r"행사\s*관리\s*업체",
    # 영상 촬영/기록·성과홍보 용역 — 중국 산시성 플라스틱 폐기물 프로젝트 "Full-process
    # Video Documentation & Outcome Promotion Services" 사례. 설계·감리가 아니라
    # 사업 전과정 영상기록·홍보 제작 용역이라 다산 전문영역과 무관.
    r"video documentation", r"outcome promotion",
    r"planos? de comunica[çc][ãa]o", r"estrat[ée]gia (e planos? )?de comunica[çc][ãa]o",
    # 이주대책계획(RAP)/토지수용/사회안전장치(social safeguards) 컨설팅.
    # 도로/댐 등 인프라 사업 산하 공고라 INCLUDE에 걸려도, 실제 업무는 이주·보상·
    # 젠더 등 사회분야 전문가 영역이라 다산 전문영역(설계/조사/감리)과 다름.
    r"gender action", r"양성평등", r"genre\b", r"g[êe]nero\b",
    # 지역사회 투자사업의 "사회공학(ingénierie sociale)" NGO 용역 — 차드 RESICHAD
    # "Recrutement d'une ONG pour l'ingénierie sociale des investissements" 사례.
    # "ingénierie"라는 단어가 있어도 토목설계가 아니라 지역사회 참여·사회적 매개를
    # 담당하는 NGO 용역이라 다산 전문영역과 무관.
    r"ing[ée]nierie sociale", r"recrutement d[\'’]?une ong",
    r"agricultur(e|al) value chain", r"농업 가치사슬",
    # 사회안전망/현금성 지원 프로그램 평가·설계 (사회보호 정책 분야, 토목 아님)
    r"social safety net", r"filets? sociaux", r"cash transfer", r"transferts? mon[ée]taires?",
    r"safety net program", r"social protection (system|program)",
    r"social inspection", r"vulnerable people",
    r"cybersecurity", r"cyber security", r"cybers[ée]curit[ée]", r"ciberseguridad",
    r"\bICT\b", r"information and communications technology",
    r"digital transformation", r"digital integration", r"e-government",
    r"digital\s+\w+\s+acceleration", r"digital\s+acceleration", r"digital economy", r"digital government",
    r"e-governance", r"smart government",
    r"digital skills? (and competence )?framework", r"digital competence framework",
    r"ict competenc\w* framework", r"digital literacy framework", r"national digital skills",
    r"computer emergency response", r"\bCERT\b",
    # 전자정부/디지털경제 프로그램의 프랑스어 표현 (부룬디 PAFEN "économie numérique" 사례).
    # 전자조달(e-GP) 시스템 도입에 따른 변화관리(change management)/소통전략 자문도
    # 엔지니어링이 아니라 조직·IT 전환관리 성격이라 함께 제외한다.
    r"[ée]conomie num[ée]rique", r"gestion du changement",
    r"march[ée]s? publics? [ée]lectroniqu", r"\be-GP\b", r"passation [ée]lectronique",
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
    # 직원 교육훈련(formation du personnel), 원자재 정책분석(heatmap), 사회적
    # 급수연결 지원 프로그램(branchements sociaux) 등 — 물/전력 유틸리티 관련
    # 프로젝트 산하라도 실제 업무가 교육·정책분석·사회사업이라 다산 전문영역과 다름
    r"formation du personnel", r"raw materials heatmap",
    r"branchements sociaux",
    # 환경사회영향평가(ESIA/EIES)·환경사회관리계획(PGES) — 콩고/카메룬 전력망
    # 건설사업처럼 "이 업무 자체가" 환경사회영향평가 전문용역이면 제외하되,
    # 마다가스카르 톨리아라 공항처럼 예비설계·상세설계·시공감리를 포함하는 종합
    # 엔지니어링(maîtrise d'œuvre) 계약의 여러 산출물 중 하나로만 포함된 경우는
    # INCLUDE(감리/설계 등)가 있으면 그대로 살아남도록 소프트 제외로 둔다
    # (RAP/이주대책계획은 항상 하드제외이지만, ESIA는 종합설계용역에 흔히 포함되는
    # 표준 산출물이라 RAP만큼 다산 업무와 명백히 무관하지는 않음).
    r"[ée]tudes? d[’']?impact environnemental(e)? et social",
    r"plan de gestion environnementale et sociale", r"\bPGES\b", r"\bEIES\b",
    r"environmental and social impact (assessment|study)", r"\bESIA\b",
]

INSTITUTIONAL_MGMT_PATTERNS = [
    r"management support consultant", r"institutional strengthening",
    r"organizational restructuring", r"institutional review and organizational",
]
COMPREHENSIVE_DESIGN_CARVEOUT_PATTERNS = [
    r"detailed project report", r"\bDPR\b",
]
_HARD_EXCLUDE_RE = re.compile("|".join(HARD_EXCLUDE_PATTERNS), re.IGNORECASE)
_INSTITUTIONAL_MGMT_RE = re.compile("|".join(INSTITUTIONAL_MGMT_PATTERNS), re.IGNORECASE)
_COMPREHENSIVE_DESIGN_CARVEOUT_RE = re.compile("|".join(COMPREHENSIVE_DESIGN_CARVEOUT_PATTERNS), re.IGNORECASE)
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


# INCLUDE/EXCLUDE(소프트) 판단에 사용할 원문 최대 길이. 공고 맨 끝에 항상 붙는
# 담당기관 제출처 주소("Corner of Nationalist Road..." 같은 문구)에 있는 거리
# 이름이 "road" 등 INCLUDE 키워드에 우연히 걸리는 오탐(잠비아 DZAP 사례)을 막기
# 위해, INCLUDE/EXCLUDE 판단은 앞쪽 부분만 본다. 자격요건/과업범위는 보통 이
# 길이 안에 다 나오고, 주소·연락처는 항상 맨 끝에 붙기 때문.
_RELEVANCE_HEAD_CHARS = 3000

def _is_hard_excluded(combined: str) -> bool:
    if _HARD_EXCLUDE_RE.search(combined):
        return True
    if _INSTITUTIONAL_MGMT_RE.search(combined):
        if not _COMPREHENSIVE_DESIGN_CARVEOUT_RE.search(combined):
            return True
    return False
def is_relevant(*texts: str) -> bool:
    combined = " ".join(t for t in texts if t)
    if not combined:
        return True  # 판단할 정보 자체가 없으면 일단 포함 (안전하게)
    # HARD_EXCLUDE는 원문 전체(길이 제한 없이)로 검사한다. 자격요건 섹션이 길어서
    # 배제 신호(예: "institutional strengthening")가 3000자 이후에 나오는 경우도
    # 있기 때문(나이지리아 SPIN 수력 PPP 제도개선 자문 사례 — 자격요건 항목이
    # 길어서 "institutional strengthening" 문구가 뒤쪽에 있었는데, INCLUDE/EXCLUDE
    # 용으로만 앞부분을 잘라 써야지 HARD_EXCLUDE까지 잘라버리면 이런 사례를 놓친다).
    if _is_hard_excluded(combined):
        return False  # INCLUDE 키워드가 있어도 무조건 제외 (RAP, ITS, 축산 등)
    head = combined[:_RELEVANCE_HEAD_CHARS]
    if _INCLUDE_RE.search(head):
        return True
    if _EXCLUDE_RE.search(head):
        return False
    return True  # 애매하면 포함


def has_strong_relevance_signal(*texts: str) -> bool:
    """INCLUDE_PATTERNS(관개/도로/댐 등 핵심 인프라 키워드)에 확실히 걸리는지만
    판단한다. 위험국 필터처럼 "애매하면 포함" 원칙을 뒤집어야 하는 경우에 쓴다."""
    combined = " ".join(t for t in texts if t)
    if not combined:
        return False
    if _is_hard_excluded(combined):
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
    "libya", "sudan", "ukraine", "lebanon", "lebanese",
}
RISK_COUNTRIES_KR = {
    "소말리아", "아프가니스탄", "예멘", "시리아", "리비아", "수단", "우크라이나", "레바논"
}


def is_koica_without_infra_signal(agency_tag: str, *texts: str) -> bool:
    """KOICA(한국국제협력단) 공고인데 관개/도로/댐 등 핵심 인프라 키워드(INCLUDE_PATTERNS)가
    전혀 없으면 True를 반환한다. KOICA는 보건/교육/청소년역량강화/IT/평가 등 다산과
    무관한 국내 행정·개발협력 용역이 워낙 다양하게 나와서, 매번 개별 키워드를 추가하는
    대신 "KOICA인데 인프라 신호가 없으면 제외"라는 근본 규칙으로 처리한다."""
    if agency_tag != "KOICA":
        return False
    return not has_strong_relevance_signal(*texts)


def is_risk_country(country: str) -> bool:
    """World Bank API는 국가명을 "Somalia, Federal Republic of"처럼 풀네임으로
    줄 때가 많아서 정확히 일치(exact match)하면 놓친다. 그래서 포함(contains)
    방식으로 판단하되, "South Sudan"/"남수단"이 "Sudan"/"수단"의 부분 문자열이라
    잘못 걸리지 않도록 먼저 명시적으로 예외 처리한다."""
    if not country:
        return False
    c = country.strip()
    cl = c.lower()
    if "south sudan" in cl or "남수단" in c:
        return False
    if any(name in c for name in RISK_COUNTRIES_KR):
        return True
    return any(name in cl for name in RISK_COUNTRIES_EN)
