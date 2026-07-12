"""관세청 화장품 수출입 금액 수집기.

공공데이터포털(data.go.kr) 관세청_품목별 수출입실적(GW) API에서
HS Code 3304(화장품: 미용·메이크업 및 기초화장용 제품류) 월별 수출입 금액을
가져와 data/trend_customs_trade.json 에 저장합니다.

확인된 응답 구조 (2026.07 실제 응답으로 검증됨):
  엔드포인트: https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList
  파라미터: serviceKey, strtYymm(YYYYMM), endYymm(YYYYMM), hsSgn(HS코드)
  ※ 조회기간은 1년(12개월) 이내만 허용됨
  응답: XML, item 목록. 한 달에 HS코드 10자리 세부품목 13개가 개별 행으로 옴
        (예: 3304101000=립스틱, 3304991000=기초화장용 제품류 등)
        마지막에 year="총계" 행은 조회기간 전체 합계이므로 제외하고,
        연월(year, "YYYY.MM")별로 expDlr(수출, 미화$)·impDlr(수입, 미화$)를 합산합니다.

필요 환경변수:
  DATA_GO_KR_SERVICE_KEY
(data.go.kr 회원가입 후 "관세청_품목별 수출입실적(GW)" 활용신청 시 발급)
"""
import os
import sys
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from utils import BASE_DIR

API_URL = "https://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
TREND_PATH = os.path.join(BASE_DIR, "data", "trend_customs_trade.json")
DOCS_TREND_PATH = os.path.join(BASE_DIR, "docs", "data", "trend_customs_trade.json")
HS_CODE = "3304"  # 화장품(미용·메이크업용 및 기초화장용 제품류)
MONTHS_BACK = 12  # API 제약: 조회기간 1년(12개월) 이내만 허용


def month_offset(yyyymm, offset):
    """"YYYYMM" 문자열에서 offset개월 전/후 계산."""
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    total = y * 12 + (m - 1) + offset
    return f"{total // 12}{(total % 12) + 1:02d}"


def run():
    api_key = os.environ.get("DATA_GO_KR_SERVICE_KEY")
    if not api_key:
        print(
            "[오류] DATA_GO_KR_SERVICE_KEY 환경변수가 없습니다.\n"
            "README의 '관세청 수출입 금액 연동' 안내를 참고해 발급받고,\n"
            "GitHub 저장소 Settings > Secrets and variables > Actions 에 등록하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    end_prd = datetime.now().strftime("%Y%m")
    start_prd = month_offset(end_prd, -(MONTHS_BACK - 1))

    params = {
        "serviceKey": api_key,
        "strtYymm": start_prd,
        "endYymm": end_prd,
        "hsSgn": HS_CODE,
    }

    resp = None
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(API_URL, params=params, timeout=30)
            break
        except requests.exceptions.RequestException as e:
            last_error = e
            print(f"[재시도 {attempt + 1}/3] 연결 실패: {e}", file=sys.stderr)
            time.sleep(5)

    if resp is None:
        print(f"[오류] 관세청 API 연결 3회 시도 모두 실패: {last_error}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"[오류] 관세청 API 요청 실패: {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        sys.exit(1)

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"[오류] 관세청 API 응답 XML 파싱 실패: {e}\n{resp.text[:300]}", file=sys.stderr)
        sys.exit(1)

    result_code = root.findtext(".//resultCode")
    if result_code != "00":
        msg = root.findtext(".//resultMsg")
        print(f"[오류] 관세청 API 응답 이상: resultCode={result_code} {msg}", file=sys.stderr)
        sys.exit(1)

    monthly = {}
    for item in root.findall(".//item"):
        year = item.findtext("year")
        if not year or year == "총계":
            continue
        try:
            exp_v = int(item.findtext("expDlr"))
            imp_v = int(item.findtext("impDlr"))
        except (TypeError, ValueError):
            continue
        period = year.replace(".", "-")
        agg = monthly.setdefault(period, {"export_usd": 0, "import_usd": 0})
        agg["export_usd"] += exp_v
        agg["import_usd"] += imp_v

    points = [
        {"period": p, "export_usd": v["export_usd"], "import_usd": v["import_usd"]}
        for p, v in sorted(monthly.items())
    ]

    os.makedirs(os.path.dirname(TREND_PATH), exist_ok=True)
    with open(TREND_PATH, "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(DOCS_TREND_PATH), exist_ok=True)
    with open(DOCS_TREND_PATH, "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=2)

    print(f"완료: 화장품 수출입 금액 {len(points)}개월치 저장 (data/trend_customs_trade.json)")


if __name__ == "__main__":
    run()
