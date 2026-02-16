---
name: skill-self-optimizer
description: 各Modeの動作ログを蓄積し、Roocode自体の設定を自己改善するための提案を行う。
---

# Skill: Self-Optimizer

## Overview
このスキルは、エージェントの「自己進化」を支える基盤です。動作中の重要な判断や結果を構造化データとして記録し、それらを分析して `.roo/` 配下の設定ファイルに対する改善案（diff）を生成します。

## Capabilities
1. **Log Decision**: 各Modeの思考プロセス、ツール実行結果、および判断理由を特定のテンプレートに従って記録します。
2. **Analyze & Propose**: 蓄積されたログファイルを読み込み、改善が必要な箇所を特定して修正案を提示します。

## Usage Guidelines

### 1. Log Decision (ロギング)
各Modeは、重要な分岐点や想定外の結果に遭遇した際、以下のテンプレートに従ってログを出力してください。
出力先: `.ops/audit_logs/self_optimization.json`

**Template (JSON format)**:
```json
{
  "timestamp": "ISO8601",
  "issue_id": "current_issue_id",
  "mode": "current_mode",
  "decision_point": "何を判断したか",
  "reasoning": "なぜそう判断したか",
  "outcome": "成功/失敗/予期せぬ結果",
  "improvement_hint": "将来的にどう変えればより良くなるか"
}
```

### 2. Analyze & Propose (改善提案)
`/self-optimize` コマンドが実行された際、以下の手順で処理を行います。
1. 指定された（または推論された）ログファイルをロードします。
2. ログ内の `improvement_hint` や失敗パターンを分析します。
3. 関連する `.roo/rules-*.md` または `SKILL.md` の内容と比較します。
4. 具体的な修正案を `git diff` 形式のテキスト、または `replace` ツールの入力形式でユーザーに提示します。

## Constraints
- GLM-4.5-air の制限を考慮し、ログは極限まで簡潔にしてください。
- 改善案は必ず人間の承認を経てから反映してください。
