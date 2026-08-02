# EOI Tracker — 해외사업 공고 취합 대시보드 (v1)

World Bank 공식 조달 공고 API를 매일 자동으로 수집해서, GitHub Pages 웹페이지로 보여주는 도구입니다.
완전 무료, 서버 관리 불필요 (GitHub가 대신 실행해줍니다).

## 현재 버전 범위
- ✅ World Bank (공식 공개 API, 로그인 불필요) — EOI, IFB, GPN, SPN, RFP 5종 공고
- ⏳ ADB — 사이트가 자동 접근을 차단(robots.txt)하고 있어 현재 버전엔 미포함. 별도 방식 필요 (아래 "향후 확장" 참고)
- ⏳ AIIB, EIB, EBRD, EDCF, KOICA, JICA, IDB, AfDB — 순차적으로 사이트 구조 확인 후 추가 예정

## 설치 방법 (최초 1회, 5~10분)

### 1. GitHub 계정 생성
https://github.com 에서 이메일로 가입 (이미 있으면 건너뛰기)

### 2. 새 저장소(repository) 만들기
1. GitHub 로그인 후 우측 상단 `+` → `New repository`
2. Repository name: `eoi-tracker` (원하는 이름으로 변경 가능)
3. `Public` 선택 (GitHub Pages 무료 버전은 Public 저장소 필요)
4. `Create repository` 클릭

### 3. 이 폴더의 파일 업로드
1. 방금 만든 저장소 페이지에서 `uploading an existing file` 클릭
2. 이 폴더(`eoi-tracker`) 안의 파일/폴더를 전부 드래그 앤 드롭
   - `.github/workflows/daily-fetch.yml`
   - `scripts/fetch_notices.py`
   - `data/notices.json`
   - `index.html`
   - `README.md`
3. `Commit changes` 클릭

### 4. GitHub Actions 쓰기 권한 켜기
1. 저장소 상단 `Settings` 탭
2. 왼쪽 메뉴 `Actions` → `General`
3. 맨 아래 `Workflow permissions`에서 `Read and write permissions` 선택 후 저장

### 5. GitHub Pages 켜기
1. `Settings` → 왼쪽 메뉴 `Pages`
2. `Build and deployment` → `Source`를 `GitHub Actions`로 설정

### 6. 첫 수집 수동 실행
1. 저장소 상단 `Actions` 탭
2. 왼쪽에서 `Daily EOI Notice Fetch` 클릭
3. 오른쪽 `Run workflow` 버튼 → `Run workflow` 클릭
4. 1~2분 후 완료되면 `data/notices.json`에 실제 데이터가 채워지고, 웹페이지가 배포됩니다

### 7. 대시보드 접속
`Settings` → `Pages`에 표시되는 주소로 접속
(보통 `https://[깃허브아이디].github.io/eoi-tracker/` 형태)

이후로는 **매일 한국시간 오전 6시**에 자동으로 갱신됩니다. 수동으로 바로 갱신하고 싶으면 `Actions` 탭에서 `Run workflow`를 다시 누르면 됩니다.

## 향후 확장 (기관 추가)

기관마다 웹사이트 구조가 달라서 하나씩 확인 후 스크립트를 추가해야 합니다. 우선순위 정해서 말씀해주시면 다음 항목부터 진행 가능합니다:

- **ADB**: robots.txt 차단으로 직접 스크래핑 불가 → ADB 이메일 알림 구독 후 그 이메일을 파싱하는 방식, 또는 공식 데이터 다운로드(XLSX) 활용 검토 필요
- **AIIB, EIB, EBRD**: 사이트 구조 조사 필요 (공개 API 유무 확인 안 됨)
- **EDCF, KOICA**: 국내 기관이라 접근성은 좋을 수 있으나 별도 확인 필요
- 필요하면 관심 국가/분야 키워드로 자동 필터링 기능도 추가 가능

## 파일 구성
```
eoi-tracker/
├── .github/workflows/daily-fetch.yml   # 매일 자동 실행 설정
├── scripts/fetch_notices.py            # World Bank API 수집 스크립트
├── data/notices.json                   # 수집된 공고 데이터 (자동 갱신됨)
├── index.html                          # 대시보드 웹페이지
└── README.md                           # 이 파일
```
