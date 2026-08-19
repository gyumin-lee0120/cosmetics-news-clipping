"""해외 화장품 매체 RSS 수집기.

config.yaml의 sources.overseas_media.feeds 목록에 등록된 RSS 피드를 순회하며
기사를 수집하고, 메인/서브 주제 및 카테고리를 태깅합니다. (해외 기사이므로 is_overseas: True)

필요 환경변수: 없음 (RSS는 공개 피드라 별도 인증이 필요 없습니다)
"""
import sys
import xml.etree.ElementTree as ET

import requests

from utils import (
    classify_categories,
    classify_topic,
    find_brand_mentions,
    load_config,
    save_news,
    strip_html,
)


def fetch_feed(name, url):
    """RSS 피드 하나를 가져와 기사 리스트로 파싱. 실패해도 예외를 던지지 않고 빈 리스트 반환."""
    try:
        resp = requests.get(
            url, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; cosmetics-news-clipping/1.0)"},
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [경고] '{name}' RSS 요청 실패: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  [경고] '{name}' RSS 파싱 실패: {e}", file=sys.stderr)
        return []

    items = []
    for item_el in root.findall(".//item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        pub_date = (item_el.findtext("pubDate") or "").strip()
        description = strip_html(item_el.findtext("description") or "")
        if not title or not link:
            continue
        items.append({"title": title, "link": link, "pub_date": pub_date, "description": description})
    return items


def run():
    cfg = load_config()
    src_cfg = cfg["sources"].get("overseas_media", {})
    if not src_cfg.get("enabled", False):
        print("overseas_media 소스가 비활성화되어 있습니다 (config.yaml sources.overseas_media.enabled: false).")
        return

    feeds = src_cfg.get("feeds", [])
    if not feeds:
        print("[경고] config.yaml sources.overseas_media.feeds 에 등록된 RSS가 없습니다.")
        return

    collected = {}
    for feed in feeds:
        name = feed.get("name", feed.get("url", "unknown"))
        url = feed["url"]
        print(f"수집 중: {name}")
        raw_items = fetch_feed(name, url)
        for raw in raw_items:
            title = raw["title"]
            description = raw["description"]
            link = raw["link"]
            combined_text = f"{title} {description}"

            own_hits, competitor_hits = find_brand_mentions(combined_text, cfg)

            item = {
                "title": title,
                "summary": description[:300],
                "link": link,
                "source": name,
                "pub_date": raw["pub_date"],
                "matched_keyword": "",
                "topic": classify_topic(combined_text, cfg),
                "categories": classify_categories(combined_text, cfg),
                "own_brand_mentions": own_hits,
                "competitor_mentions": competitor_hits,
                "is_overseas": True,
            }
            collected[link] = item

    merged = save_news(list(collected.values()))
    print(f"완료: 이번 실행 {len(collected)}건 수집, 누적 저장 {len(merged)}건 (data/news.json, docs/data/news.json)")


if __name__ == "__main__":
    run()
