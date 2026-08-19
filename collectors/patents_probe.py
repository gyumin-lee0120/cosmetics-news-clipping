"""KIPRIS Plus 2차 진단 — totalCount 위치와 연도 필터 방식 확인.

1차 진단으로 word/docsStart/docsCount/patent/utility 가 유효함을 확인했습니다.
이번에는 (1) 전체 건수 필드가 응답 어디에 있는지, (2) 연도(출원일자) 필터를
어떤 파라미터로 거는지를 확인합니다.

필요 환경변수: KIPRIS_SERVICE_KEY
호출 횟수: 6회
"""
import os
import re
import sys

import requests

BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"

CASES = [
    ("A. getWordSearch (기준)", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "docsStart": "1", "docsCount": "1"}),
    ("B. getAdvancedSearch + inventionTitle", f"{BASE}/getAdvancedSearch",
     {"inventionTitle": "엑소좀", "docsStart": "1", "docsCount": "1"}),
    ("C. getAdvancedSearch + astrtCont", f"{BASE}/getAdvancedSearch",
     {"astrtCont": "엑소좀", "docsStart": "1", "docsCount": "1"}),
    ("D. getAdvancedSearch + applicationDate 범위", f"{BASE}/getAdvancedSearch",
     {"astrtCont": "엑소좀", "applicationDate": "20240101~20241231",
      "docsStart": "1", "docsCount": "1"}),
    ("E. getAdvancedSearch + applicationDate 연도만", f"{BASE}/getAdvancedSearch",
     {"astrtCont": "엑소좀", "applicationDate": "2024", "docsStart": "1", "docsCount": "1"}),
    ("F. getWordSearch + patent/utility 조합", f"{BASE}/getWordSearch",
     {"word": "엑소좀", "patent": "true", "utility": "false",
      "docsStart": "1", "docsCount": "1"}),
]


def probe(label, url, params, service_key):
    params = dict(params)
    params["ServiceKey"] = service_key
    print("=" * 70)
    print(label)
    shown = {k: ("***" if k == "ServiceKey" else v) for k, v in params.items()}
    print(f"  파라미터: {shown}")
    try:
        resp = requests.get(url, params=params, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"  요청 실패: {e}")
        return
    body = resp.text.replace(service_key, "***")
    print(f"  HTTP {resp.status_code} / 응답 길이 {len(body)}자")

    # 건수로 보이는 태그를 전부 뽑아본다
    counts = re.findall(r"<(\w*[Cc]ount\w*)>([^<]*)</\1>", body)
    print(f"  count 계열 태그: {counts if counts else '없음'}")

    # resultCode / resultMsg
    for tag in ("resultCode", "resultMsg", "successYN"):
        m = re.search(rf"<{tag}>([^<]*)</{tag}>", body)
        print(f"  {tag}: {m.group(1) if m else '(없음)'}")

    print("  응답 마지막 600자:")
    print("  " + body[-600:].replace("\n", "\n  "))
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
