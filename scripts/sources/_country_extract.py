# -*- coding: utf-8 -*-
"""
공고 제목/본문 텍스트에서 국가명을 찾아내는 공통 유틸리티.
나라장터, 건엔협, KIND, ICAK처럼 "국가" 필드를 별도로 안 주는 국내 사이트에서
제목 텍스트만으로 실제 사업 대상국을 추정할 때 사용한다.

※ 대시보드 국가 필터가 소스마다 언어(영어/한국어)가 뒤섞여서 뜨는 문제가 있어서,
   텍스트 안에서는 한글로 국가명을 찾되(이게 우리가 가진 목록이라), 최종적으로
   반환하는 값은 World Bank 등 해외 소스와 표기를 맞추기 위해 영어로 바꿔서 준다.

완벽하지 않을 수 있음(제목에 국가명이 없으면 못 찾음, 두 나라가 같이 언급되면
먼저 나오는 것/긴 이름 우선으로 하나만 선택) — 참고용으로 쓸 것.
"""

# 긴 이름을 먼저 매칭해야 짧은 이름에 잘못 걸리는 걸 방지할 수 있어서,
# 아래 리스트는 사용 시점에 길이순으로 정렬해서 검사한다.
_COUNTRY_NAMES = [
    # 동남아시아
    "동티모르", "티모르레스테", "베트남", "캄보디아", "라오스", "미얀마", "태국",
    "필리핀", "인도네시아", "말레이시아", "브루나이", "싱가포르",
    # 남아시아
    "네팔", "방글라데시", "스리랑카", "파키스탄", "인도", "부탄", "몰디브", "아프가니스탄",
    # 중앙아시아
    "우즈베키스탄", "카자흐스탄", "키르기스스탄", "타지키스탄", "투르크메니스탄", "몽골",
    # 중동
    "요르단", "이라크", "이란", "레바논", "예멘", "시리아", "사우디아라비아",
    "아랍에미리트", "오만", "쿠웨이트", "카타르", "팔레스타인",
    # 아프리카
    "이집트", "케냐", "우간다", "에티오피아", "탄자니아", "르완다", "가나",
    "나이지리아", "세네갈", "코트디부아르", "알제리", "모로코", "튀니지", "리비아",
    "잠비아", "짐바브웨", "모잠비크", "말라위", "카메룬", "콩고민주공화국", "콩고",
    "남아프리카공화국", "앙골라", "보츠와나", "나미비아", "마다가스카르", "부르키나파소",
    "니제르", "말리", "베냉", "토고", "감비아", "시에라리온", "라이베리아", "소말리아",
    "지부티", "수단", "남수단",
    # 유럽/코카서스
    "조지아", "아제르바이잔", "아르메니아", "우크라이나", "몰도바", "세르비아",
    "보스니아", "코소보", "북마케도니아", "알바니아", "튀르키예", "터키",
    # 중남미
    "볼리비아", "페루", "콜롬비아", "파라과이", "에콰도르", "브라질", "칠레",
    "아르헨티나", "온두라스", "과테말라", "니카라과", "엘살바도르", "코스타리카",
    "파나마", "도미니카공화국", "아이티", "자메이카",
    # 오세아니아/기타
    "파푸아뉴기니", "피지", "솔로몬제도", "바누아투", "사모아", "통가",
    "우크라이나", "중국",
]
_SORTED_NAMES = sorted(set(_COUNTRY_NAMES), key=len, reverse=True)

# 한글 국가명 -> 영어 국가명 (World Bank 등 해외 소스 표기와 통일하기 위함).
# 위 _COUNTRY_NAMES에 있는 모든 이름이 여기 빠짐없이 있어야 함.
_KOR_TO_EN = {
    "동티모르": "Timor-Leste", "티모르레스테": "Timor-Leste",
    "베트남": "Vietnam", "캄보디아": "Cambodia", "라오스": "Laos", "미얀마": "Myanmar",
    "태국": "Thailand", "필리핀": "Philippines", "인도네시아": "Indonesia",
    "말레이시아": "Malaysia", "브루나이": "Brunei", "싱가포르": "Singapore",
    "네팔": "Nepal", "방글라데시": "Bangladesh", "스리랑카": "Sri Lanka",
    "파키스탄": "Pakistan", "인도": "India", "부탄": "Bhutan", "몰디브": "Maldives",
    "아프가니스탄": "Afghanistan",
    "우즈베키스탄": "Uzbekistan", "카자흐스탄": "Kazakhstan",
    "키르기스스탄": "Kyrgyzstan", "타지키스탄": "Tajikistan",
    "투르크메니스탄": "Turkmenistan", "몽골": "Mongolia",
    "요르단": "Jordan", "이라크": "Iraq", "이란": "Iran", "레바논": "Lebanon",
    "예멘": "Yemen", "시리아": "Syria", "사우디아라비아": "Saudi Arabia",
    "아랍에미리트": "United Arab Emirates", "오만": "Oman", "쿠웨이트": "Kuwait",
    "카타르": "Qatar", "팔레스타인": "Palestine",
    "이집트": "Egypt", "케냐": "Kenya", "우간다": "Uganda", "에티오피아": "Ethiopia",
    "탄자니아": "Tanzania", "르완다": "Rwanda", "가나": "Ghana", "나이지리아": "Nigeria",
    "세네갈": "Senegal", "코트디부아르": "Côte d'Ivoire", "알제리": "Algeria",
    "모로코": "Morocco", "튀니지": "Tunisia", "리비아": "Libya", "잠비아": "Zambia",
    "짐바브웨": "Zimbabwe", "모잠비크": "Mozambique", "말라위": "Malawi",
    "카메룬": "Cameroon", "콩고민주공화국": "Democratic Republic of Congo",
    "콩고": "Congo", "남아프리카공화국": "South Africa", "앙골라": "Angola",
    "보츠와나": "Botswana", "나미비아": "Namibia", "마다가스카르": "Madagascar",
    "부르키나파소": "Burkina Faso", "니제르": "Niger", "말리": "Mali", "베냉": "Benin",
    "토고": "Togo", "감비아": "Gambia", "시에라리온": "Sierra Leone",
    "라이베리아": "Liberia", "소말리아": "Somalia", "지부티": "Djibouti",
    "수단": "Sudan", "남수단": "South Sudan",
    "조지아": "Georgia", "아제르바이잔": "Azerbaijan", "아르메니아": "Armenia",
    "우크라이나": "Ukraine", "몰도바": "Moldova", "세르비아": "Serbia",
    "보스니아": "Bosnia and Herzegovina", "코소보": "Kosovo",
    "북마케도니아": "North Macedonia", "알바니아": "Albania",
    "튀르키예": "Türkiye", "터키": "Türkiye",
    "볼리비아": "Bolivia", "페루": "Peru", "콜롬비아": "Colombia",
    "파라과이": "Paraguay", "에콰도르": "Ecuador", "브라질": "Brazil", "칠레": "Chile",
    "아르헨티나": "Argentina", "온두라스": "Honduras", "과테말라": "Guatemala",
    "니카라과": "Nicaragua", "엘살바도르": "El Salvador", "코스타리카": "Costa Rica",
    "파나마": "Panama", "도미니카공화국": "Dominican Republic", "아이티": "Haiti",
    "자메이카": "Jamaica",
    "파푸아뉴기니": "Papua New Guinea", "피지": "Fiji",
    "솔로몬제도": "Solomon Islands", "바누아투": "Vanuatu", "사모아": "Samoa",
    "통가": "Tonga", "중국": "China",
}


def extract_country(*texts: str) -> str:
    """주어진 텍스트(들)에서 국가명을 찾아 영어로 반환한다. 못 찾으면 빈 문자열."""
    combined = " ".join(t for t in texts if t)
    if not combined:
        return ""
    for name in _SORTED_NAMES:
        if name in combined:
            return _KOR_TO_EN.get(name, name)
    return ""
