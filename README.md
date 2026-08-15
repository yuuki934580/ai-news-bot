# AIニュース自動収集・記事化・Discord投稿システム

毎日、AI業界の重要ニュースを自動収集 → 評価・選定 → 記事化 → Discordに投稿します。

## 1. 必要なアカウント

- Anthropic（Claude API利用のため）: https://console.anthropic.com
- Discordサーバー（投稿先チャンネルの管理権限が必要）
- GitHubアカウント（自動実行させる場合。ローカル実行のみなら不要）

## 2. OpenAI APIキーの取得

1. https://platform.openai.com/api-keys にログイン
2. 「Create new secret key」
3. 発行されたキー（`sk-...`）をコピーしておく（このページを閉じると再表示できないので注意）
4. 「Billing」で少額のクレジットを追加しておく（従量課金）

## 3. Discord Webhookの作成

1. 投稿したいチャンネルの設定（歯車アイコン）を開く
2. 「連携サービス」→「ウェブフック」→「新しいウェブフック」
3. 名前を設定し、「ウェブフックURLをコピー」
4. このURLは他人に見られないよう厳重に管理する（漏洩すると誰でも投稿できてしまいます）

## 4. ローカルでのセットアップ

```bash
# 1. リポジトリを取得（またはこのフォルダをそのまま使用）
cd ai-news-bot

# 2. 仮想環境を作成（推奨）
python3 -m venv venv
source venv/bin/activate   # Windowsの場合: venv\Scripts\activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数ファイルを作成
cp .env.example .env
```

`.env` をテキストエディタで開き、以下を書き換える:

```
OPENAI_API_KEY=sk-（取得したキー）
DISCORD_WEBHOOK_URL=（取得したWebhook URL）
```

## 5. テスト実行

```bash
python main.py
```

- ログは標準出力と `state/run.log` の両方に出力されます
- 初回はニュースが多く見つかるはずですが、閾値（`config.yaml` の `min_score_threshold`）を超えなければ投稿はスキップされます。まずはテストのため一時的に `min_score_threshold` を `3` 程度に下げて動作確認することをおすすめします
- 正常に動けばDiscordチャンネルに記事が投稿されます

## 6. 毎日自動実行する方法（GitHub Actions）

1. このフォルダの中身をGitHubリポジトリにプッシュする（**`.env` は絶対にコミットしないこと**。`.gitignore` 済みですが念のため確認してください）
2. リポジトリの `Settings` → `Secrets and variables` → `Actions` → `New repository secret` で以下を登録:
   - `OPENAI_API_KEY`
   - `DISCORD_WEBHOOK_URL`
3. `Settings` → `Actions` → `General` → `Workflow permissions` を「Read and write permissions」に変更（state保存のコミットに必要）
4. これで毎日 JST 6:00（`.github/workflows/daily.yml` の cron設定）に自動実行されます
5. 実行時刻を変えたい場合は `.github/workflows/daily.yml` の `cron: "0 21 * * *"` を編集してください（UTC表記です。JST = UTC+9、つまり JST時刻 − 9 = UTC設定値）
6. `Actions` タブから「Run workflow」で手動実行してテストすることもできます

## 7. 設定のカスタマイズ（`config.yaml`）

| 項目 | 説明 |
|---|---|
| `collection.max_items_per_source` | 各ソースから取得する最大件数 |
| `collection.lookback_hours` | 何時間以内のニュースを対象にするか |
| `rss_feeds` | 固定RSSフィードのリスト（追加・削除可能） |
| `google_news_queries` | キーワード検索型ニュース収集の対象（企業名など） |
| `evaluation.min_score_threshold` | 記事化する最低スコア（0〜10） |
| `evaluation.max_articles_per_day` | 1日の最大掲載件数 |
| `dedup.lookback_days` | 何日以内の既出ニュースを重複とみなすか |
| `claude.model` | 使用するClaudeモデル |

## 8. トラブルシューティング

- **投稿が来ない**: `state/run.log` を確認。「候補ニュースが0件」「新規ニュースがない」「閾値を超える重要ニュースがなかった」のいずれかのログがあれば正常動作（該当日はニュースが少なかっただけ）
- **RSS取得エラーが出る**: 一部の企業公式ブログはRSS URLが変更されることがあります。`config.yaml` の `rss_feeds` を更新するか、`google_news_queries` 経由の収集に任せてください
- **Discord投稿が失敗する**: Webhook URLが正しいか、チャンネルが削除されていないか確認してください
- **文字化けする**: ターミナルの文字コードがUTF-8になっているか確認してください

## 9. 注意事項

- APIキー・Webhook URLは絶対にコード内に直接書かない、公開リポジトリにコミットしないでください
- 個人利用を想定したシンプルな構成です。負荷分散や高可用性は考慮していません
