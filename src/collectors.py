"""RSS / Google Newsからニュース候補を収集する"""
import logging
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import feedparser

logger = logging.getLogger("ai_news_bot.collectors")


@dataclass
class NewsCandidate:
    title: str
    url: str
    summary: str
    source: str
    published_at: str = ""  # ISO文字列。取得できない場合は空文字


def _entry_to_candidate(entry, source_name: str) -> NewsCandidate:
    published_at = ""
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            published_at = datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            break

    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    return NewsCandidate(
        title=getattr(entry, "title", "(タイトルなし)"),
        url=getattr(entry, "link", ""),
        summary=summary[:1000],
        source=source_name,
        published_at=published_at,
    )


def _is_within_lookback(candidate: NewsCandidate, lookback_hours: int) -> bool:
    if not candidate.published_at:
        # 公開日時が取れない場合は候補として残す（後段の重複判定に任せる）
        return True
    try:
        published = datetime.fromisoformat(candidate.published_at)
    except ValueError:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    return published >= cutoff


def fetch_rss_feed(name: str, url: str, max_items: int, lookback_hours: int) -> list[NewsCandidate]:
    """単一RSSフィードを取得する。失敗しても例外を投げず空リストを返す"""
    try:
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            logger.warning("RSS取得に失敗（パースエラー）: %s (%s)", name, url)
            return []

        candidates = []
        for entry in parsed.entries[:max_items]:
            candidate = _entry_to_candidate(entry, name)
            if candidate.url and _is_within_lookback(candidate, lookback_hours):
                candidates.append(candidate)
        return candidates
    except Exception as exc:  # ネットワークエラー等、想定外の失敗も飲み込んで継続する
        logger.error("RSS取得中に例外発生: %s (%s) -> %s", name, url, exc)
        return []


def fetch_google_news(name: str, query: str, locale: dict, max_items: int, lookback_hours: int) -> list[NewsCandidate]:
    """Googleニュースの検索型RSSを取得する"""
    encoded_query = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search?q={encoded_query}"
        f"&hl={locale.get('hl', 'ja')}&gl={locale.get('gl', 'JP')}&ceid={locale.get('ceid', 'JP:ja')}"
    )
    return fetch_rss_feed(f"Google News: {name}", url, max_items, lookback_hours)


def collect_all(config: dict) -> list[NewsCandidate]:
    """config.yamlの設定に従い、全ソースからニュース候補を収集する"""
    collection_cfg = config.get("collection", {})
    max_items = collection_cfg.get("max_items_per_source", 10)
    lookback_hours = collection_cfg.get("lookback_hours", 30)

    all_candidates: list[NewsCandidate] = []

    for feed_cfg in config.get("rss_feeds", []):
        items = fetch_rss_feed(feed_cfg["name"], feed_cfg["url"], max_items, lookback_hours)
        logger.info("収集: %s -> %d件", feed_cfg["name"], len(items))
        all_candidates.extend(items)
        time.sleep(0.5)  # 連続リクエストを避ける

    locale = config.get("google_news_locale", {})
    for q_cfg in config.get("google_news_queries", []):
        items = fetch_google_news(q_cfg["name"], q_cfg["query"], locale, max_items, lookback_hours)
        logger.info("収集: Google News[%s] -> %d件", q_cfg["name"], len(items))
        all_candidates.extend(items)
        time.sleep(0.5)

    return all_candidates
