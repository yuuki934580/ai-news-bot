"""
AIニュース自動収集・記事化・Discord投稿システム
実行: python main.py
"""
import logging
import sys

from src.config import CONFIG, SETTINGS, STATE_FILE, LOG_FILE
from src.collectors import collect_all
from src.dedup import load_state, save_state, filter_new_candidates, record_posted
from src.evaluator import evaluate_candidates, select_top_candidates
from src.article_generator import generate_article
from src.discord_poster import post_to_discord

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ai_news_bot.main")


def run() -> None:
    logger.info("========== AIニュース収集バッチ開始 ==========")

    # 1. 収集
    try:
        candidates = collect_all(CONFIG)
    except Exception as exc:
        logger.error("収集フェーズで致命的エラー、処理を中断します: %s", exc)
        return
    logger.info("収集完了: 候補 %d件", len(candidates))

    if not candidates:
        logger.warning("候補ニュースが0件のため終了します")
        return

    # 2. 重複除去
    state = load_state(STATE_FILE)
    dedup_cfg = CONFIG.get("dedup", {})
    new_candidates = filter_new_candidates(
        candidates, state, dedup_cfg.get("lookback_days", 14)
    )

    if not new_candidates:
        logger.info("新規ニュースがないため終了します")
        return

    # 3. 評価
    openai_cfg = CONFIG.get("openai", {})
    evaluations = evaluate_candidates(
        new_candidates,
        api_key=SETTINGS.openai_api_key,
        model=openai_cfg.get("model", "gpt-4o"),
        max_tokens=openai_cfg.get("evaluation_max_tokens", 4000),
    )

    if not evaluations:
        logger.warning("評価に失敗またはゼロ件のため終了します")
        return

    # 4. 選定
    eval_cfg = CONFIG.get("evaluation", {})
    selected = select_top_candidates(
        evaluations,
        min_score_threshold=eval_cfg.get("min_score_threshold", 6),
        max_articles=eval_cfg.get("max_articles_per_day", 6),
    )

    if not selected:
        if eval_cfg.get("skip_if_no_candidates", True):
            logger.info("閾値を超える重要ニュースがなかったため、本日は投稿をスキップします")
            return

    # 5. 記事生成
    article = generate_article(
        selected,
        api_key=SETTINGS.openai_api_key,
        model=openai_cfg.get("model", "gpt-4o"),
        max_tokens=openai_cfg.get("article_max_tokens", 8000),
    )

    if not article:
        logger.error("記事生成に失敗したため投稿をスキップします")
        return

    # 6. Discord投稿
    discord_cfg = CONFIG.get("discord", {})
    posted = post_to_discord(
        article,
        webhook_url=SETTINGS.discord_webhook_url,
        max_length=discord_cfg.get("max_message_length", 1900),
        username=discord_cfg.get("username", "AI新聞Bot"),
    )

    if not posted:
        logger.error("Discord投稿に失敗しました。状態は更新しません（次回再試行されます）")
        return

    # 7. 状態保存（投稿できたものだけ既出として記録）
    posted_items = [
        {"url": item["candidate"].url, "title": item["candidate"].title} for item in selected
    ]
    state = record_posted(state, posted_items, dedup_cfg.get("max_history_items", 500))
    save_state(STATE_FILE, state)

    logger.info("投稿完了: %d件のニュースを記事化しました", len(selected))
    logger.info("========== AIニュース収集バッチ終了 ==========")


if __name__ == "__main__":
    run()
