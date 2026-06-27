# memcp — Agent Memory

Long-term memory for AI coding agents. Stores Claude Code sessions in SQLite and exposes them via MCP so agents can search their own history across sessions.

```
"JWTの実装、先週どうやったっけ？" → search_memory("JWT authentication") → 過去セッションを即返答
```

## What it does

Claude Code はセッションをまたいで過去の作業を覚えていません。memcp はそのギャップを埋めます。

- セッション終了時に自動でログを SQLite に取り込む
- MCP ツール経由で Claude Code から過去セッションを検索・参照できる
- ローカルのみ動作、クラウド依存なし

## Requirements

- macOS / Linux
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Claude Code

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-username/memcp.git
cd memcp
uv sync

# 2. One-command setup
uv run memcp setup
```

`memcp setup` が以下を全部やります:

| Step | 内容 |
|------|------|
| 1 | `~/.agent-memory/` ディレクトリを作成 |
| 2 | SQLite データベースを初期化 |
| 3 | `~/.claude.json` に MCP サーバーを登録 |
| 4 | `~/.claude/settings.json` に SessionEnd フックを追加 |

**3. Claude Code を再起動** — これで完了です。

次のセッションから、終了時に自動でメモリに保存されます。

## How it works

```
Claude Code session ends
        ↓
SessionEnd hook fires
        ↓
memcp ingest-new  ←  ~/.claude/projects/**/*.jsonl をスキャン
        ↓
SQLite FTS5 index に格納
        ↓
次のセッションで search_memory("...") が使えるようになる
```

## MCP Tools

Claude Code から自動で呼び出されます。明示的に呼ぶこともできます。

| Tool | 説明 |
|------|------|
| `search_memory(query)` | キーワードで過去セッションを全文検索 |
| `read_session(session_id, query)` | セッションの会話を読む（query で絞り込み可） |
| `list_recent_sessions(limit)` | 最近のセッション一覧 |
| `ingest_session(path)` | 特定の `.jsonl` を手動で取り込む |

### 使用例

```
過去のJWT実装を教えて
→ search_memory("JWT authentication") が自動で呼ばれる

先週のdevpayプロジェクトで何をやってた？
→ search_memory("devpay") → read_session(...) で詳細を参照
```

## CLI Commands

```bash
# セットアップ（初回のみ）
memcp setup

# 新しいセッションをまとめて取り込む
memcp ingest-new

# 特定ファイルを取り込む
memcp ingest ~/.claude/projects/myproject/abc123.jsonl
```

## Data stored

```
~/.agent-memory/
├── database.sqlite   # セッション / メッセージ / ツールコール
└── logs/             # (将来: 生ログアーカイブ)
```

データはすべてローカルの SQLite に保存されます。外部送信はありません。

## Development

```bash
uv sync --dev

# テスト
uv run pytest

# リント・フォーマット
uv run ruff check . --fix
uv run ruff format .

# 型チェック
uv run mypy src/
```

## Roadmap

- [ ] Cursor / GitHub Copilot 対応
- [ ] embedding ベースのセマンティック検索
- [ ] メモリ抽出（セッションから事実を蒸留）
- [ ] `memcp status` — 取り込み状況の確認コマンド

## License

MIT — see [LICENSE](LICENSE)
