# 화장품 시장 뉴스 클리핑 시스템 — 인수인계 문서

> 새 AI 어시스턴트에게 이 문서를 그대로 붙여넣으면 이어서 작업할 수 있습니다.
> 작성일: 2026-09-02

---

## 1. 프로젝트 개요

**목적**: 원텍(Wontech) 미래전략실용 화장품 시장 뉴스·통계 자동 수집 및 대시보드

- 메인 주제: 더마 스킨케어 · 홈뷰티 디바이스
- 서브 주제: 화장품 시장 전체
- **핵심 제약: 전 과정 비용 0원** (무료 API·무료 호스팅만 사용)

**리소스**

| 항목 | 위치 |
|---|---|
| GitHub 저장소 | `gyumin-lee0120/cosmetics-news-clipping` |
| 대시보드 (GitHub Pages) | https://gyumin-lee0120.github.io/cosmetics-news-clipping/ |
| 텔레그램 봇 | `@wontech_cosmetic_bot` (이름: cosmeticbot) |
| 외부 스케줄러 | cron-job.org (무료) |

---

## 2. 저장소 구조

```
cosmetics-news-clipping/
├── .github/workflows/
│   ├── collect.yml              # 매일 07:30 KST 데이터 수집
│   └── telegram_briefing.yml    # 텔레그램 발송 (workflow_dispatch 전용)
├── collectors/
│   ├── utils.py                 # 공용: 설정 로드, 주제/카테고리 분류, 저장
│   ├── naver_news.py            # 네이버 뉴스 API
│   ├── overseas_media.py        # 해외 매체 RSS
│   ├── kosis_online_shopping.py # 통계청 온라인쇼핑 거래액
│   ├── customs_trade.py         # 관세청 수출입 금액
│   └── patents.py               # KIPRIS Plus 특허 출원 트렌드
├── data/                        # 수집 결과 JSON (원본)
│   ├── news.json
│   ├── trend_online_shopping.json
│   ├── trend_customs_trade.json
│   ├── production_stats.json    # 식약처 생산실적 (수동 갱신)
│   ├── patent_trend.json
│   └── exhibitions.json         # 전시회 일정 (수동 관리)
├── docs/                        # GitHub Pages 루트
│   ├── index.html               # 대시보드 (단일 파일, CSS·JS 인라인)
│   ├── data/                    # data/ 의 사본 (대시보드가 읽음)
│   └── logo-*.png               # 원텍/올리지오 로고
├── config.yaml                  # 키워드·소스 설정
├── send_email.py                # 이메일 브리핑 (현재 비활성)
├── send_telegram.py             # 텔레그램 브리핑
└── requirements.txt
```

---

## 3. GitHub Secrets (등록 완료)

| Secret | 용도 |
|---|---|
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | 네이버 뉴스 검색 API |
| `KOSIS_API_KEY` | 통계청 KOSIS |
| `DATA_GO_KR_SERVICE_KEY` | 공공데이터포털 (관세청) |
| `KIPRIS_SERVICE_KEY` | KIPRIS Plus 특허 API |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 텔레그램 발송 |
| `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` | 이메일 (현재 미사용) |

---

## 4. 자동화 동작 방식

### 데이터 수집 (collect.yml)
매일 07:30 KST (`cron: "30 22 * * *"`, UTC 기준). 스텝 순서:

1. 네이버 뉴스 수집
2. 해외 매체 뉴스 수집 *(continue-on-error)*
3. 특허 출원 트렌드 수집 *(continue-on-error)*
4. 통계청 온라인쇼핑 거래액 *(continue-on-error)*
5. 관세청 수출입 금액 *(continue-on-error)*
6. 이메일 브리핑 발송 (config에서 비활성)
7. 변경사항 커밋 및 푸시

### 텔레그램 브리핑
**중요**: GitHub Actions의 `schedule:` 트리거는 지연·누락이 잦아 **제거했습니다.**
대신 `telegram_briefing.yml`은 `workflow_dispatch`만 두고, **cron-job.org**가 평일 09:13 KST에
GitHub REST API를 호출해 실행합니다.

```
POST https://api.github.com/repos/gyumin-lee0120/cosmetics-news-clipping/actions/workflows/telegram_briefing.yml/dispatches
Authorization: Bearer <fine-grained PAT, Actions 읽기/쓰기 권한>
Accept: application/vnd.github+json
Body: {"ref":"main"}
crontab: 13 9 * * 1-5  (타임존 Asia/Seoul)
```

---

## 5. API 스펙 메모 (실호출로 확인한 것)

### KIPRIS Plus 특허 API
- 엔드포인트: `https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch`
- 파라미터: `astrtCont`(초록) 또는 `inventionTitle`(발명의명칭), `applicationDate=YYYY0101~YYYY1231`, `docsStart`, `docsCount`, `ServiceKey`
- 응답: XML, 맨 끝 `<count><totalCount>N</totalCount></count>`
- **주의**: `getWordSearch`에는 `year` 파라미터가 없음 (넣으면 `INVALID_REQUEST_PARAMETER_ERROR`). `numOfRows`/`pageNo`도 미지원
- 무료 한도 월 1,000회 → 과거 연도는 JSON에 캐시하고 올해치만 매일 갱신하는 구조

### 해외 매체 RSS
- Global Cosmetics News: `https://www.globalcosmeticsnews.com/feed/` (정상)
- CosmeticsDesign Europe/Asia: 서비스 종료됨 (제외)

---

## 6. 뉴스 아이템 스키마

```json
{
  "title": "...",
  "summary": "...",
  "link": "...",
  "source": "네이버 뉴스",
  "pub_date": "Thu, 13 Aug 2026 05:00:00 +0000",
  "matched_keyword": "...",
  "topic": "main | sub",
  "categories": ["원료", "디바이스·기술"],
  "own_brand_mentions": [],
  "competitor_mentions": [],
  "is_overseas": false
}
```

`utils.py`의 `save_news()`가 link 기준 중복 제거 후 90일치만 보관하고,
`data/news.json` 과 `docs/data/news.json` 양쪽에 저장합니다.

---

## 7. 대시보드 기능 (docs/index.html)

단일 HTML 파일. CSS·JS 모두 인라인. 외부 라이브러리 없음.

- 3단 레이아웃: 카테고리 내비 / 뉴스 목록 / 캘린더·전시회·특허
- 상단 트렌드 카드 3종 (온라인쇼핑, 생산실적, 수출입)
- 탭: 메인 주제 / 화장품 시장 전체
- 기간 필터: 오늘 / 주간 / 월간
- 카테고리 필터 + **출처 필터(전체/국내/해외)**
- 제목 텍스트 검색
- KPI 카드 클릭 시 해당 기사만 필터링 + 30일 추이 스파크라인
- 다크모드 수동 토글 (localStorage 저장)
- 스켈레톤 로딩, 모바일 카테고리 드롭다운
- 원텍 CI 로고 클릭 = 새로고침
- 특허 출원 트렌드 카드 (최근 2개 연도는 공개 지연으로 반투명 처리)

---

## 8. 알려진 이슈 · 주의사항

1. **특허 데이터 해석**: 특허는 출원 후 약 1년 6개월 뒤 공개되므로 최근 2개 연도는 실제보다 적게 집계됨. 추세 판단은 그 이전 연도 기준으로 해야 함.
2. **KOSIS 간헐적 타임아웃**: `kosis.kr` 연결이 가끔 실패. `continue-on-error`라 파이프라인은 안 깨지고 기존 데이터 유지.
3. **영문 기사 분류**: `classify_topic()`이 config.yaml 키워드 substring 매칭 방식. 영문 키워드를 추가했지만 해외 기사 상당수가 여전히 `sub`로 분류됨. 개선 여지 있음.
4. **"미분류" 비중이 높음**: 카테고리 키워드 보강 필요.
5. **substring 매칭 함정**: 짧은 키워드는 오탐 발생. 예) `AI`는 "h**ai**r", "av**ai**lable"에도 걸려서 `인공지능`/`artificial intelligence`로 교체함. 키워드 추가 시 주의.
6. **cron-job.org 지연**: 무료 플랜이라 몇 분씩 밀릴 수 있음.
7. **식약처 생산실적**: 연 1회 발표라 `data/production_stats.json` 수동 갱신 필요.
8. **KOSIS 온라인쇼핑**: 월 1회 수동 확인 권장.

---

## 9. 남은 백로그

`config.yaml`에서 `enabled: false`로 남아있는 소스들:

- `bigkinds` — 빅카인즈 오픈API
- `cosmetics_trade_press_rss` — 코스인·코스모닝·CMN 등 국내 화장품 전문지 RSS
- `mfds_cosmetics_regulation` — 식약처 화장품 규제정보 API
- `mfds_medical_device` — 식약처 의료기기 품목허가정보 API **(홈뷰티 디바이스 경쟁사 인허가 동향 파악용 — 실무 가치 높음)**
- `wipo_patentscope` — WIPO PatentScope RSS

기타 개선 아이디어:
- 특허 키워드 조정 (현재 "스킨부스터"는 3건뿐 — 특허 명세서에서 안 쓰는 마케팅 용어라서)
- 브리핑 요약문을 단순 집계에서 자연어 생성으로 개선

---

## 10. 작업 방식 안내 (새 AI에게)

사용자는 개발자가 아니며 **GitHub 웹 편집기로 직접 파일을 수정**합니다. 로컬 개발 환경이나 git CLI를 쓰지 않습니다.

따라서:

- 코드는 **전체 파일 또는 명확한 블록 단위**로 제공할 것. "이 줄을 이렇게 바꾸세요" 식의 단편적 지시는 붙여넣기 사고가 잦았음
- 수정 위치는 `Ctrl+F`로 찾을 검색어를 함께 알려줄 것
- 실제로 겪은 사고들: YAML 들여쓰기 오류, 파이썬 파일에 YAML 내용 붙여넣기, 파일 끝부분 누락, GitHub 편집기 파일명 칸을 건드려 `index.html`이 다른 이름으로 바뀜
- 변경 후에는 GitHub Actions 로그나 실제 대시보드로 검증할 것

사용자 요청 사항:
- 자료는 정확성이 중요. **출처와 증빙을 함께 제시**할 것
- 추정이 섞이면 **추정임을 명시**하고 근거를 밝힐 것
- 확인되지 않은 내용을 사실처럼 제시하지 말 것
