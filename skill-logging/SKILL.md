---
name: skill-logging
description: 動作結果と期待値の乖離を JSON および Markdown 形式で記録する。
---

# Skill: Logging (JSON/Markdown)

## Definition
- 本 Skill は、セッションやタスクの実行結果を標準化された形式で記録するための純粋な手続きである。
- 記録される内容は、事後の監査および自動分析に利用される。

## Input Contract
- **Parameters**:
    - `session_id`: セッションの一意識別子。
    - `goal`: セッションまたはタスクの期待される成果。
    - `result`: 実際の実行結果。
    - `gap`: 期待値と結果の乖離（具体的記述）。
    - `action`: 次回に向けた改善アクション。
    - `source_mode`: 実行した Mode (pm, code, reviewer 等)。
    - `protocol_fidelity`: 設計された通信プロトコルを遵守したか (true/false)。
    - `format`: 出力形式 (`markdown` | `json` | `both`)。デフォルトは `both`。
- **Constraint**: `goal`, `result`, `session_id`, `source_mode` が不足している場合、Skill はエラーを返す。

## Procedure (Stateless)
1.  **保存先ディレクトリの確認**: 
    - Markdown: `development_logs/`
    - JSON: `.ops/audit_logs/sessions/`
    ディレクトリが存在することを確認し、なければ作成する。
2.  **Markdown 出力の生成 (format が markdown または both の場合)**:
    - ファイル名: `development_logs/session-[session_id].md`
    - 内容:
        ```markdown
        # Session Audit Log: [session_id]
        - **Date**: [Current Date]
        - **Mode**: [source_mode]
        - **Goal**: [goal]
        - **Result**: [result]
        - **Expectation Gap**: [gap]
        - **Action for Improvement**: [action]
        ```
3.  **JSON 出力の生成 (format が json または both の場合)**:
    - ファイル名: `.ops/audit_logs/sessions/session-[session_id].json`
    - 内容:
        ```json
        {
          "session_id": "[session_id]",
          "timestamp": "[Current ISO Timestamp]",
          "source_mode": "[source_mode]",
          "audit": {
            "goal": "[goal]",
            "result": "[result]",
            "expectation_gap": "[gap]",
            "improvement_action": "[action]",
            "protocol_fidelity": [protocol_fidelity]
          }
        }
        ```
4.  **ファイル書き込み**: 生成されたコンテンツを指定されたパスに保存する。

## Output Contract
- **Result**: 指定された形式でのログファイル生成完了。
- **Artifacts**:
    - `development_logs/session-[session_id].md` (Human-readable)
    - `.ops/audit_logs/sessions/session-[session_id].json` (Audit Evidence)