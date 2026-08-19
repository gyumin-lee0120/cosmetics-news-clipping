"""KIPRIS Plus getWordSearch 파라미터 진단용 임시 스크립트.

여러 파라미터 조합으로 호출해보고 각각의 원본 응답을 출력합니다.
어떤 조합이 통하는지 확인한 뒤에는 이 파일과 워크플로 스텝을 삭제하세요.

필요 환경변수: KIPRIS_SERVICE_KEY
호출 횟수: 아래 CASES 개수만큼 (기본 7회) — 월 1,000회 한도에 거의 영향 없음
"""
import os
import sys

import requests

BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"

CASES = [
    ("A. word만", f"{BASE}/getWordSearch", {"word": "엑소좀"}),
    ("B. word + docsStart/docsCount", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "docsStart": "1", "docsCount": "10"}),
    ("C. word + patent/utility", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "patent": "true", "utility": "true"}),
    ("D. word + patent/utility + docsStart/docsCount", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "patent": "true", "utility": "true", "docsStart": "1", "docsCount": "10"}),
    ("E. word + year", f"{BASE}/getWordSearch", {"word": "엑소좀", "year": "2024"}),
    ("F. word + numOfRows/pageNo", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "numOfRows": "10", "pageNo": "1"}),
    ("G. 영문 파라미터 searchWord", f"{BASE}/getWordSearch", {"searchWord": "엑소좀"}),
]


def probe(label, url, params, service_key):
    params = dict(params)
    params["ServiceKey"] = service_key
    print("=" * 70)
    print(label)
    # 키가 로그에 노출되지 않도록 마스킹해서 출력
    shown = {k: ("***" if k == "ServiceKey" else v) for k, v in params.items()}
    print(f"  파라미터: {shown}")
    try:
        resp = requests.get(url, params=params, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"  요청 실패: {e}")
        return
    print(f"  HTTP {resp.status_code}")
    body = resp.text.replace(service_key, "***")
    print("  응답(앞 800자):")
    print("  " + body[:800].replace("\n", "\n  "))
    print()


def main():
    service_key = os.environ.get("KIPRIS_SERVICE_KEY")
    if not service_key:
        print("[오류] KIPRIS_SERVICE_KEY 환경변수가 없습니다.", file=sys.stderr)
        sys.exit(1)

    for label, url, params in CASES:
        probe(label, url, params, service_key)


if __name__ == "__main__":
    main()
