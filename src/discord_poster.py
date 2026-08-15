"""生成した記事をDiscord Webhookへ投稿する（2000字制限に対応して分割送信）"""
import logging
import time

import requests

logger = logging.getLogger("ai_news_bot.discord_poster")


def split_article(article: str, max_length: int) -> list[str]:
    """記事を"---"区切りを優先しつつ、max_length以下のチャンクに分割する"""
    blocks = article.split("\n---\n")
    chunks: list[str] = []
    current = ""

    for block in blocks:
        candidate = (current + "\n---\n" + block) if current else block
        if len(candidate) <= max_length:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # ブロック自体が長すぎる場合は強制的に分割する
            if len(block) > max_length:
                for i in range(0, len(block), max_length):
                    chunks.append(block[i:i + max_length])
                current = ""
            else:
                current = block

    if current:
        chunks.append(current)

    return chunks


def post_to_discord(
    article: str, webhook_url: str, max_length: int, username: str = "AI新聞Bot"
) -> bool:
    """記事をDiscordに投稿する。一部失敗してもエラーをログに残して継続する"""
    chunks = split_article(article, max_length)
    if not chunks:
        logger.warning("投稿するチャンクがありません")
        return False

    success_count = 0
    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(
                webhook_url,
                json={"content": chunk, "username": username},
                timeout=15,
            )
            if resp.status_code in (200, 204):
                success_count += 1
            else:
                logger.error(
                    "Discord投稿失敗 (chunk %d/%d): status=%s body=%s",
                    i + 1, len(chunks), resp.status_code, resp.text[:500],
                )
        except requests.RequestException as exc:
            logger.error("Discord投稿中に例外発生 (chunk %d/%d): %s", i + 1, len(chunks), exc)

        time.sleep(1)  # Discordのレート制限対策

    if success_count == 0:
        return False
    if success_count < len(chunks):
        logger.warning("一部のメッセージ投稿に失敗しました (%d/%d 成功)", success_count, len(chunks))
    return True
