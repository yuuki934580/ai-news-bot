"""OpenAI APIを使ってニュース候補の重要度・新規性・信頼性を評価し、選定する"""
import json
import logging
import re

from openai import OpenAI

from src.collectors import NewsCandidate

logger = logging.getLogger("ai_news_bot.evaluator")

EVALUATION_SYSTEM_PROMPT = """あなたはAI業界を長年取材しているシニア編集者です。
与えられたニュース候補それぞれについて、以下の観点で0〜10点のスコールと簡潔な理由を付けてください。

評価観点（重要性・新規性・AI業界への影響・社会への影響・今後の技術発展への影響・企業/市場への影響・話題性を総合して1つのスコアにする）:
- 単なる小ニュースの羅列ではなく「後から振り返って重要だったと思えるか」を重視する
- 一次情報（公式発表・論文・信頼できる報道）に基づくものを優先する
- 同じ話題の重複や、単なる噂・憶測ベースの記事は低く評価する

出力は必ず以下のJSON形式のみで返してください。説明文やMarkdown装飾は一切含めないでください。

{
  "evaluations": [
    {"index": 0, "score": 8, "reason": "評価理由を一文で"},
    {"index": 1, "score": 3, "reason": "評価理由を一文で"}
  ]
}
"""


def _build_user_prompt(candidates: list[NewsCandidate]) -> str:
    lines = ["以下はニュース候補のリストです。各項目のindexに対応させて評価してください。\n"]
    for i, c in enumerate(candidates):
        lines.append(
            f"[index {i}]\nタイトル: {c.title}\n出典: {c.source}\n概要: {c.summary}\nURL: {c.url}\n"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """モデル出力からJSON部分を頑健に抽出する"""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def evaluate_candidates(
    candidates: list[NewsCandidate],
    api_key: str,
    model: str,
    max_tokens: int,
) -> list[dict]:
    """候補ニュースを評価する。失敗時は空リストを返し、呼び出し側で「今日は候補なし」扱いにする"""
    if not candidates:
        return []

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=5)

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(candidates)},
            ],
        )
        raw_text = response.choices[0].message.content or ""
        parsed = _extract_json(raw_text)
        evaluations = parsed.get("evaluations", [])
    except Exception as exc:
        logger.error("評価API呼び出し/パースに失敗しました: %s", exc)
        return []

    results = []
    for ev in evaluations:
        idx = ev.get("index")
        if idx is None or not (0 <= idx < len(candidates)):
            continue
        results.append(
            {
                "candidate": candidates[idx],
                "score": ev.get("score", 0),
                "reason": ev.get("reason", ""),
            }
        )
    return results


def select_top_candidates(
    evaluations: list[dict], min_score_threshold: int, max_articles: int
) -> list[dict]:
    """スコア閾値と最大件数に従って選定する。水増しはしない"""
    qualified = [e for e in evaluations if e["score"] >= min_score_threshold]
    qualified.sort(key=lambda e: e["score"], reverse=True)
    selected = qualified[:max_articles]
    logger.info(
        "選定: 候補%d件中、閾値%d以上が%d件、最終選定%d件",
        len(evaluations), min_score_threshold, len(qualified), len(selected),
    )
    return selected
