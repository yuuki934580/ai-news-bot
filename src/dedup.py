"""既出ニュースの管理と重複除去"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.collectors import NewsCandidate

logger = logging.getLogger("ai_news_bot.dedup")


def _normalize_title(title: str) -> str:
    """タイトル類似判定のための簡易正規化（記号・空白除去、小文字化）"""
    normalized = re.sub(r"[^\w一-龥ぁ-んァ-ヶ]", "", title)
    return normalized.lower()


def load_state(state_file: Path) -> dict:
    if not state_file.exists():
        return {"items": []}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("状態ファイルの読み込みに失敗、初期状態から開始します: %s", exc)
        return {"items": []}


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def filter_new_candidates(
    candidates: list[NewsCandidate], state: dict, lookback_days: int
) -> list[NewsCandidate]:
    """既出のURL・類似タイトルを除外して新規候補のみ返す"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    seen_urls = set()
    seen_titles = set()
    for item in state.get("items", []):
        try:
            posted_at = datetime.fromisoformat(item["posted_at"])
        except (KeyError, ValueError):
            continue
        if posted_at >= cutoff:
            seen_urls.add(item["url"])
            seen_titles.add(_normalize_title(item["title"]))

    new_candidates = []
    seen_in_batch = set()  # 今回の収集内での重複（同じニュースが複数ソースにヒットするケース）も除去
    for c in candidates:
        if not c.url or c.url in seen_urls or c.url in seen_in_batch:
            continue
        norm_title = _normalize_title(c.title)
        if norm_title in seen_titles or norm_title in seen_in_batch:
            continue
        seen_in_batch.add(c.url)
        seen_in_batch.add(norm_title)
        new_candidates.append(c)

    logger.info("重複除去: %d件 -> %d件", len(candidates), len(new_candidates))
    return new_candidates


def record_posted(state: dict, posted_items: list[dict], max_history_items: int) -> dict:
    """投稿済みニュースを状態に追記し、履歴が肥大化しないよう古いものから間引く"""
    now = datetime.now(timezone.utc).isoformat()
    for item in posted_items:
        state.setdefault("items", []).append(
            {"url": item["url"], "title": item["title"], "posted_at": now}
        )
    if len(state["items"]) > max_history_items:
        state["items"] = state["items"][-max_history_items:]
    return state
