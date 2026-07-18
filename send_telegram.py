"""텔레그램 아침 브리핑 발송 스크립트.

매일 GitHub Actions에서 데이터 수집 직후 실행되어,
오늘의 뉴스 헤드라인 · KPI 지표 · 트렌드 데이터 · 다가오는 전시회를
텔레그램 메시지 한 통으로 요약해 보냅니다.

필요 환경변수:
  TELEGRAM_BOT_TOKEN  (BotFather에서 발급받은 봇 토큰)
  TELEGRAM_CHAT_ID    (메시지를 받을 개인/그룹 채팅 ID)

두 값이 없으면 조용히 건너뜁니다 (아직 봇 설정 전이어도 파이프라인은 안 깨지도록).
"""
import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "collectors"))
from utils import load_config, load_existing, BASE_DIR  # noqa: E402

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
DASHBOARD_URL = "https://gyumin-lee0120.github.io/cosmetics-news-clipping/"
KST = timezone(timedelta(hours=9))

DATA_DIR = os.path.join(BASE_DIR, "data")


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_recent(item, hours=30):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        return parsedate_to_datetime(item["pub_date"]) >= cutoff
    except (KeyError, TypeError, ValueError):
        return False


def months_before_period(period, n):
    y, m = (int(x) for x in period.split("-"))
    total = y * 12 + (m - 1) - n
    ny, nm = divmod(total, 12)
    return f"{ny}-{nm + 1:02d}"


def build_kpi_section(today_items, all_recent_items, cfg):
    main_items = [i for i in today_items if i.get("topic") == "main"]
    own_hits = [i for i in today_items if i.get("own_brand_mentions")]
    competitor_hits = [i for i in today_items if i.get("competitor_mentions")]

    main_share = round(len(main_items) / len(today_items) * 100) if today_items else 0

    cat_counts = {}
    for i in main_items:
        for c in i.get("categories", []):
            cat_counts[c] = cat_counts.get(c, 0) + 1
    top_cat = max(cat_counts.items(), key=lambda x: x[1]) if cat_counts else None

    lines = [
        "📊 <b>오늘의 지표</b> (더마 스킨케어·홈뷰티 기준)",
        f"자사 브랜드 언급: {len(own_hits)}건",
        f"경쟁사 언급: {len(competitor_hits)}건",
        f"메인 주제 비중: {main_share}%",
        f"최다 카테고리: {top_cat[0] + f' ({top_cat[1]}건)' if top_cat else '–'}",
    ]
    return "\n".join(lines)


def build_trend_section():
    lines = ["📈 <b>트렌드 데이터</b>"]

    online = load_json("trend_online_shopping.json")
    if online:
        latest = online[-1]
        year_ago = next((p for p in online if p["period"] == months_before_period(latest["period"], 12)), None)
        compare = year_ago or online[0]
        growth = (
            ((latest["value_million_krw"] - compare["value_million_krw"]) / compare["value_million_krw"]) * 100
            if compare["value_million_krw"] else None
        )
        trillion = latest["value_million_krw"] / 1_000_000
        growth_txt = f", 전년동월比 {growth:+.1f}%" if year_ago and growth is not None else ""
        lines.append(f"· 온라인쇼핑 거래액: {trillion:.2f}조원 ({latest['period']}{growth_txt})")
    else:
        lines.append("· 온라인쇼핑 거래액: 데이터 없음")

    prod = load_json("production_stats.json")
    if prod:
        latest = prod[-1]
        prev = prod[-2] if len(prod) > 1 else None
        growth = (
            ((latest["value_100m_krw"] - prev["value_100m_krw"]) / prev["value_100m_krw"]) * 100
            if prev and prev["value_100m_krw"] else None
        )
        trillion = latest["value_100m_krw"] / 10000
        growth_txt = f", 전년比 {growth:+.1f}%" if growth is not None else ""
        lines.append(f"· 국내 생산실적: {trillion:.2f}조원 ({latest['year']}{growth_txt})")
    else:
        lines.append("· 국내 생산실적: 데이터 없음")

    customs = load_json("trend_customs_trade.json")
    if customs:
        latest = customs[-1]
        exp_m = latest["export_usd"] / 1_000_000
        imp_m = latest["import_usd"] / 1_000_000
        lines.append(f"· 수출입 금액: 수출 {exp_m:.1f}백만$ / 수입 {imp_m:.1f}백만$ ({latest['period']})")
    else:
        lines.append("· 수출입 금액: 데이터 없음")

    return "\n".join(lines)


def build_news_section(today_items, sub_count_today):
    main_items = [i for i in today_items if i.get("topic") == "main"]
    lines = [f"📰 <b>주요 뉴스 헤드라인</b> (최근 24시간, 메인 {len(main_items)}건 / 서브 {sub_count_today}건)"]
    if not main_items:
        lines.append("메인 주제(더마 스킨케어·홈뷰티) 관련 신규 기사가 없습니다.")
        return "\n".join(lines)

    for i, item in enumerate(main_items[:5], start=1):
        title = html.escape(item["title"])
        source = html.escape(item.get("source", ""))
        lines.append(f'{i}. <a href="{item["link"]}">{title}</a> ({source})')
    return "\n".join(lines)


def build_exhibitions_section():
    exhibitions = load_json("exhibitions.json")
    today = datetime.now(KST).date()
    upcoming = sorted(
        (e for e in exhibitions if datetime.strptime(e["end_date"], "%Y-%m-%d").date() >= today),
        key=lambda e: e["start_date"],
    )[:2]

    lines = ["🗓️ <b>다가오는 전시회</b>"]
    if not upcoming:
        lines.append("예정된 전시회가 없습니다.")
        return "\n".join(lines)

    for e in upcoming:
        name = html.escape(e["name"])
        lines.append(f"· {name} ({e['start_date']} ~ {e['end_date']})")
    return "\n".join(lines)


def build_message(cfg):
    all_items = load_existing()
    today_items = [i for i in all_items if is_recent(i, hours=30)]
    sub_count_today = len([i for i in today_items if i.get("topic") == "sub"])

    today_str = datetime.now(KST).strftime("%Y-%m-%d (%a)")
    header = f"🧴 <b>화장품 시장 뉴스 클리핑</b> [아침 브리핑]\n{today_str}"

    sections = [
        header,
        "",
        build_news_section(today_items, sub_count_today),
        "",
        build_kpi_section(today_items, all_items, cfg),
        "",
        build_trend_section(),
        "",
        build_exhibitions_section(),
        "",
        f'📌 <a href="{DASHBOARD_URL}">대시보드 전체 보기</a>',
    ]
    return "\n".join(sections)


def send(token, chat_id, text):
    resp = requests.post(
        TELEGRAM_API.format(token=token),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def run():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print(
            "[안내] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 없어 텔레그램 발송을 건너뜁니다.\n"
            "README의 '텔레그램 봇 설정' 안내를 참고해 발급받고 GitHub secrets에 등록하세요."
        )
        return

    cfg = load_config()
    message = build_message(cfg)

    try:
        send(token, chat_id, message)
        print("텔레그램 브리핑 발송 완료")
    except requests.exceptions.RequestException as e:
        print(f"[오류] 텔레그램 발송 실패: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
