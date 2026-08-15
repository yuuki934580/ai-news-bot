"""設定ファイル(config.yaml)と環境変数(.env)の読み込みを行う"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")


def load_config() -> dict:
    config_path = ROOT_DIR / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class Settings:
    """環境変数から読み込む秘密情報・実行時設定"""

    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self.discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY が設定されていません。.env または GitHub Secrets を確認してください。"
            )
        if not self.discord_webhook_url:
            raise RuntimeError(
                "DISCORD_WEBHOOK_URL が設定されていません。.env または GitHub Secrets を確認してください。"
            )


SETTINGS = Settings()
CONFIG = load_config()
STATE_FILE = ROOT_DIR / "state" / "seen_news.json"
LOG_FILE = ROOT_DIR / "state" / "run.log"
