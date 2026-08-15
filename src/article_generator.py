"""選定済みニュースから、指定フォーマットのDiscord投稿用記事を生成する"""
import logging
from datetime import datetime

from openai import OpenAI

logger = logging.getLogger("ai_news_bot.article_generator")

ARTICLE_SYSTEM_PROMPT = """あなたはAI業界専門のジャーナリストです。
与えられたニュース情報をもとに、AIに関心のある一般的な読者向けの記事をMarkdownで作成してください。

# 厳守事項
- 「すごいニュースです」「AI業界に大きな影響を与えそうです」のような中身のない表現は禁止
- 事実と推測を明確に区別すること。推測を書く場合は「〜と考えられる」「〜の可能性がある」と明示する
- 出典URLは必ずそのまま正確に記載する（改変しない）
- 与えられた情報の範囲で書き、憶測で事実を捏造しない
- 各ニュースについて「何が起きたのか」「なぜ重要なのか」「今後どうなりそうか」を必ず含める
- 最後に「今日のAI業界の流れ」（ニュース同士の関係性の分析）と「今日の注目ポイント」（3点程度）を書く

# 出力フォーマット（この構造を厳守すること）

# 今日のAIニュース
{date}

## 今日の重要ニュース

### 1. (ニュースタイトル)

**何が起きたのか：**
(説明)

**なぜ重要なのか：**
(説明)

**今後どうなりそうか：**
(説明)

**出典：** (URL)

---

(以下、件数分繰り返し)

## 今日のAI業界の流れ

(分析)

## 今日の注目ポイント

- (ポイント1)
- (ポイント2)
- (ポイント3)
"""


def _build_user_prompt(selected: list[dict], date_str: str) -> str:
    lines = [f"日付: {date_str}\n", "以下のニュースをもとに記事を作成してください。\n"]
    for i, item in enumerate(selected, 1):
        c = item["candidate"]
        lines.append(
            f"[ニュース{i}]\nタイトル: {c.title}\n出典元: {c.source}\n"
            f"概要: {c.summary}\nURL: {c.url}\n評価理由: {item['reason']}\n"
        )
    return "\n".join(lines)


def generate_article(
    selected: list[dict],
    api_key: str,
    model: str,
    max_tokens: int,
) -> str | None:
    """記事本文（Markdown文字列）を生成する。失敗時はNoneを返す"""
    if not selected:
        return None

    date_str = datetime.now().strftime("%Y年%m月%d日")
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": ARTICLE_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(selected, date_str)},
            ],
        )
        article = response.choices[0].message.content or ""
        return article.strip()
    except Exception as exc:
        logger.error("記事生成API呼び出しに失敗しました: %s", exc)
        return None
