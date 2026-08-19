"""KIPRIS Plus 특허·실용신안 출원 트렌드 수집기.

config.yaml의 sources.kipris_patents.keywords 에 등록된 키워드별로
연도별 특허·실용신안 건수(totalCount)를 조회해 data/patent_trend.json 에 저장합니다.

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
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from utils import BASE_DIR, load_config

API_URL = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"
KST = timezone(timedelta(hours=9))

DATA_PATH = os.path.join(BASE_DIR, "data", "patent_trend.json")
DOCS_DATA_PATH = os.path.join(BASE_DIR, "docs", "data", "patent_trend.json")


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


def find_text(root, tag):
    """네임스페이스 유무와 무관하게 첫 번째로 발견되는 태그의 텍스트 반환."""
    for el in root.iter():
        if el.tag.split("}")[-1] == tag:
            return (el.text or "").strip()
    return None


def fetch_count(service_key, word, year):
    """키워드+연도 조건으로 검색해 totalCount 반환. 실패 시 None."""
    params = {
        "word": word,
        "year": str(year),
        "patent": "true",
        "utility": "true",
        "numOfRows": "1",     # 건수만 필요하므로 최소로 요청
        "pageNo": "1",
        "ServiceKey": service_key,
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=20)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [경고] '{word}' {year}년 요청 실패: {e}", file=sys.stderr)
        return None

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        print(f"  [경고] '{word}' {year}년 응답 파싱 실패. 응답 앞부분: {resp.text[:300]}", file=sys.stderr)
        return None

    result_code = find_text(root, "resultCode")
    if result_code is not None and result_code not in ("00", "000", "0"):
        result_msg = find_text(root, "resultMsg") or "(메시지 없음)"
        print(f"  [경고] '{word}' {year}년 API 오류 resultCode={result_code}: {result_msg}", file=sys.stderr)
        return None

    total = find_text(root, "totalCount")
    if total is None:
        print(f"  [경고] '{word}' {year}년 totalCount를 찾지 못했습니다. 응답 앞부분: {resp.text[:300]}", file=sys.stderr)
        return None

    try:
        return int(total)
    except ValueError:
        print(f"  [경고] '{word}' {year}년 totalCount 값이 숫자가 아닙니다: {total!r}", file=sys.stderr)
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

    years_back = int(src_cfg.get("years_back", 6))
    this_year = datetime.now(KST).year
    years = list(range(this_year - years_back + 1, this_year + 1))

    cache = load_existing()
    calls = 0
    failures = 0

    for word in keywords:
        for year in years:
            # 올해는 매번 갱신, 과거 연도는 캐시에 있으면 건너뜀 (호출 절약)
            if year != this_year and (word, year) in cache:
                continue
            count = fetch_count(service_key, word, year)
            calls += 1
            if count is None:
                failures += 1
                continue
            cache[(word, year)] = count
            print(f"  {word} / {year}년: {count}건")

    rows = sorted(
        ({"keyword": k, "year": y, "count": c} for (k, y), c in cache.items()),
        key=lambda r: (r["keyword"], r["year"]),
    )
    save(rows)

    print(
        f"완료: API 호출 {calls}회 (실패 {failures}회), "
        f"저장 {len(rows)}건 (data/patent_trend.json, docs/data/patent_trend.json)"
    )
    if failures and failures == calls:
        # 전부 실패했으면 설정 문제일 가능성이 높으므로 워크플로에서 눈에 띄게 실패 처리
        sys.exit(1)


if __name__ == "__main__":
    run()
