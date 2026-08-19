"""KIPRIS Plus 특허·실용신안 출원 트렌드 수집기.

config.yaml의 sources.kipris_patents.keywords 에 등록된 키워드별로
연도별 출원 건수(totalCount)를 조회해 data/patent_trend.json 에 저장합니다.

API 스펙 (2026-08-19 실호출로 확인):
  엔드포인트: .../patUtiModInfoSearchSevice/getAdvancedSearch
  파라미터  : astrtCont(초록) 또는 inventionTitle(발명의명칭),
              applicationDate=YYYY0101~YYYY1231, docsStart, docsCount, ServiceKey
  응답      : XML, 맨 끝 <count><totalCount>N</totalCount></count>
  주의      : getWordSearch에는 year 파라미터가 없습니다
              (year를 넣으면 INVALID_REQUEST_PARAMETER_ERROR)

호출 절약 설계 (무료 한도: 월 1,000회):
  - 과거 연도는 한 번 조회하면 JSON에 캐시되어 다시 호출하지 않습니다.
  - 매 실행 시에는 '올해' 데이터만 갱신합니다.
  - 예) 키워드 6개 x 6년 = 첫 실행 36회, 이후 매일 실행해도 6회/일 (월 약 180회)

필요 환경변수:
  KIPRIS_SERVICE_KEY  (KIPRIS Plus 마이페이지 > API KEY 관리에서 발급)

키가 없으면 조용히 건너뜁니다 (파이프라인이 깨지지 않도록).
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

from utils import BASE_DIR, load_config

API_URL = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"
KST = timezone(timedelta(hours=9))

DATA_PATH = os.path.join(BASE_DIR, "data", "patent_trend.json")
DOCS_DATA_PATH = os.path.join(BASE_DIR, "docs", "data", "patent_trend.json")

# 검색 대상 필드: astrtCont(초록) = 폭넓음, inventionTitle(발명의명칭) = 좁고 정확
VALID_FIELDS = ("astrtCont", "inventionTitle")


def load_existing():
    """기존 트렌드 데이터를 {(keyword, year): count} 딕셔너리로 로드."""
    if not os.path.exists(DATA_PATH):
        return {}
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return {(r["keyword"], r["year"]): r["count"] for r in rows if "keyword" in r and "year" in r}


def fetch_count(service_key, field, keyword, year):
    """키워드+연도 조건으로 검색해 totalCount 반환. 실패 시 None."""
    params = {
        field: keyword,
        "applicationDate": f"{year}0101~{year}1231",
        "docsStart": "1",
        "docsCount": "1",
        "ServiceKey": service_key,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [경고] '{keyword}' {year}년 요청 실패: {e}", file=sys.stderr)
        return None

    body = resp.text

    m = re.search(r"<resultCode>([^<]*)</resultCode>", body)
    if m and m.group(1) not in ("00", "000", "0"):
        msg = re.search(r"<resultMsg>([^<]*)</resultMsg>", body)
        print(
            f"  [경고] '{keyword}' {year}년 API 오류 resultCode={m.group(1)}: "
            f"{msg.group(1) if msg else '(메시지 없음)'}",
            file=sys.stderr,
        )
        return None

    m = re.search(r"<totalCount>([^<]*)</totalCount>", body)
    if not m:
        safe = body.replace(service_key, "***")
        print(f"  [경고] '{keyword}' {year}년 totalCount 없음. 응답 끝부분: {safe[-300:]}", file=sys.stderr)
        return None

    try:
        return int(m.group(1))
    except ValueError:
        print(f"  [경고] '{keyword}' {year}년 totalCount가 숫자가 아님: {m.group(1)!r}", file=sys.stderr)
        return None


def save(rows):
    for path in (DATA_PATH, DOCS_DATA_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)


def run():
    service_key = os.environ.get("KIPRIS_SERVICE_KEY")
    if not service_key:
        print(
            "[안내] KIPRIS_SERVICE_KEY 환경변수가 없어 특허 수집을 건너뜁니다.\n"
            "KIPRIS Plus 마이페이지 > API KEY 관리에서 키를 발급받아 GitHub secrets에 등록하세요."
        )
        return

    cfg = load_config()
    src_cfg = cfg["sources"].get("kipris_patents", {})
    if not src_cfg.get("enabled", False):
        print("kipris_patents 소스가 비활성화되어 있습니다 (config.yaml sources.kipris_patents.enabled: false).")
        return

    keywords = src_cfg.get("keywords", [])
    if not keywords:
        print("[경고] config.yaml sources.kipris_patents.keywords 에 등록된 키워드가 없습니다.")
        return

    field = src_cfg.get("search_field", "astrtCont")
    if field not in VALID_FIELDS:
        print(f"[경고] search_field '{field}'는 지원하지 않습니다. astrtCont로 대체합니다. (가능: {VALID_FIELDS})")
        field = "astrtCont"

    years_back = int(src_cfg.get("years_back", 6))
    this_year = datetime.now(KST).year
    years = list(range(this_year - years_back + 1, this_year + 1))

    cache = load_existing()
    calls = 0
    failures = 0

    print(f"검색 필드: {field} / 대상 연도: {years[0]}~{years[-1]} / 키워드 {len(keywords)}개")

    for keyword in keywords:
        for year in years:
            # 올해는 매번 갱신, 과거 연도는 캐시에 있으면 건너뜀 (호출 절약)
            if year != this_year and (keyword, year) in cache:
                continue
            count = fetch_count(service_key, field, keyword, year)
            calls += 1
            if count is None:
                failures += 1
                continue
            cache[(keyword, year)] = count
            print(f"  {keyword} / {year}년: {count}건")
          
    rows = sorted(
        ({"keyword": k, "year": y, "count": c} for (k, y), c in cache.items()),
        key=lambda r: (r["keyword"], r["year"]),
    )
    save(rows)

    print(
        f"완료: API 호출 {calls}회 (실패 {failures}회), "
        f"저장 {len(rows)}건 (data/patent_trend.json, docs/data/patent_trend.json)"
    )
    if calls and failures == calls:
        # 전부 실패했으면 설정 문제일 가능성이 높으므로 눈에 띄게 실패 처리
        sys.exit(1)


if __name__ == "__main__":
    run()
