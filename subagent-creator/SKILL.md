---
name: subagent-creator
description: Gemini CLI のカスタムサブエージェント（カスタムモード/スキル）の作成・設定・管理を支援する。エージェントの自律性と拡張性を向上させるために使用する。
---

# Subagent Creator

このSkillは、Gemini CLI でカスタムサブエージェントを作成・設定・管理するプロセスをガイドする。

**重要：ユーザーとのすべてのやり取りは日本語で行うこと。**

---

## ワークフロー

以下のステップを順番に実行する。

### Step 1: 環境確認・セットアップ

まず、`read_file` または `run_shell_command` を使って以下を確認する。

**⓪ 過去の知見の確認**

`.gemini/skills/subagent-creator/references/known_issues.md` を `read_file` で読み込み、過去に発生した問題と対策を把握する。

**① settings.json の確認**

`~/.gemini/settings.json` を確認し、以下が含まれているかチェックする：

```json
{
  "experimental": {
    "enableAgents": true
  }
}
```

- **存在しない・設定がない場合：** ユーザーに許可を求め、`write_file` で設定を追加または作成する。

---

### Step 2: 要件のヒアリング

以下の項目を順番に確認する。

| 項目 | 質問内容 |
|---|---|
| **目的** | このサブエージェントに何をさせたいか |
| **使用ツール** | どのファイル操作・コマンド実行が必要か |
| **配置場所** | プロジェクトレベル（`.gemini/agents/`）または ユーザーレベル（`~/.gemini/agents/`） |

**② agents/ ディレクトリと既存エージェントの確認**

配置場所が確定したら、ディレクトリの存在を確認し、必要に応じて `mkdir -p` で作成する。既存のエージェントと名前が重複していないかも確認する。

---

### Step 3: サブエージェント定義の生成

ヒアリング内容をもとに、サブエージェントの定義ファイルを提案する。

**ファイル構造：**

```markdown
---
name: [小文字・ハイフン区切りの識別子]
description: [具体的で明確な説明。日本語が推奨される]
kind: local
tools:
  - [必要なツールを列挙]
model: [任意]
temperature: [任意]
---

[システムプロンプト：役割・制約・振る舞いを記述]
```

**利用可能なツール一覧：**
`read_file`, `write_file`, `replace`, `grep_search`, `glob`, `list_directory`, `run_shell_command`, `google_web_search`, `web_fetch`, `save_memory`, `ask_user`

---

### Step 4: ファイルの作成と動作確認の案内

提案した定義を `write_file` で作成し、ユーザーに動作確認（`/agents list`, `/agents refresh` など）の案内を行う。

---

### 改善ループ

このスキルの使用中にエラーや想定外の動作が発生した場合、`.gemini/skills/subagent-creator/references/known_issues.md` に知見を追記し、再発を防止する。
