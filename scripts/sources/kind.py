"""
KIND(한국해외인프라도시개발지원공사) 입찰정보 게시판 수집 스크립트
https://www.kindkorea.or.kr/pages/72

- 별도 인증/로그인 없이 접근 가능한 공개 게시판
- 목록이 서버에서 렌더링된 일반 HTML 테이블 형태 (JS 렌더링 아님)
- robots.txt 상 일반 크롤러 접근 허용 확인됨

사용법 (기존 프로젝트 구조 기준):
  scripts/sources/kind.py 로 저장 후, fetch_all.py 오케스트레이터에서
      from sources.kind import fetch_kind
      ...
      all_items += fetch_kind()
  형태로 등록하면 됩니다.

주의:
  이 스크립트는 샌드박스 네트워크 제한으로 실제 사이트에 접속해
  직접 테스트하지 못했습니다. GitHub Actions에서 처음 실행했을 때
  결과가 비어 있거나 에러가 나면, 실제 페이지의 HTML 구조(table
  선택자 등)가 아래 코드와 다를 수 있으니 그 결과를 캡처해서 다시
  요청해 주세요.
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.kindkorea.or.kr"
LIST_URL = f"{BASE_URL}/pages/72"
SOURCE_NAME = "KIND"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_kind(max_pages: int = 3):
    """
    KIND 입찰정보 게시판에서 최근 공고 목록을 가져온다.
    max_pages: 몇 페이지까지 훑을지 (게시판이 최신순 정렬이라
               너무 크게 잡을 필요 없음)
    """
    items = []

    for page in range(1, max_pages + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[KIND] 요청 실패 (page {page}): {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # 게시판 목록 테이블의 행(row)들을 찾는다.
        # 실제 페이지의 클래스명이 다를 수 있어 여러 후보를 시도한다.
        rows = soup.select("table tbody tr") or soup.select(".board-list tbody tr")

        if not rows:
            print(f"[KIND] page {page}: 목록을 찾지 못함 (선택자 확인 필요)")
            break

        page_had_items = False
        for row in rows:
            link_tag = row.find("a", href=True)
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            href = link_tag["href"]
            full_url = href if href.startswith("http") else BASE_URL + href

            # id=NNNNN 파라미터를 참조번호처럼 사용
            m = re.search(r"id=(\d+)", href)
            ref_id = m.group(1) if m else None

            # 작성일(게시일) 컬럼 추정: YYYY-MM-DD 패턴을 행 텍스트에서 탐색
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", row.get_text())
            posted_date = date_match.group(0) if date_match else None

            if not title or title in ("공지", "번호", "제목"):
                continue

            items.append(
                {
                    "source": SOURCE_NAME,
                    "title": title,
                    "url": full_url,
                    "ref_id": ref_id,
                    "posted_date": posted_date,
                    "deadline": None,  # 이 게시판은 별도 마감일 컬럼이 없음
                    "collected_at": datetime.utcnow().isoformat(),
                }
            )
            page_had_items = True

        if not page_had_items:
            break

    return items


if __name__ == "__main__":
    results = fetch_kind()
    print(f"총 {len(results)}건 수집")
    for r in results[:5]:
        print(r)
