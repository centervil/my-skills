---
name: skill-orchestration
description: AIエージェント（Mode）間の通信プロトコル（Orchestration Protocol）を定義・検証・管理するためのスキル。
---

# Skill: オーケストレーション (Orchestration)

## 概要
pmMode からの指示を各 Worker Mode にディスパッチし、成果物の検証と統合を行うための通信プロトコルを管理する。

## Instructions
1. **プロトコル定義**: `interaction_schema.yaml` に基づき、DispatchObject と ResultObject の整合性を維持する。
2. **タスクディスパッチ**: Orchestrator モードにおいて、Worker Mode への指示を構造化（YAML）して送信する。
3. **成果物検証**: Worker Mode から返された ResultObject を検証し、Success Criteria を満たしているか判定する。
4. **エスカレーション**: 判定結果が NG の場合、事実に基づいた情報を pmMode にフィードバックする。

## Output Contract
- 各 Mode 間の構造化された通信ログ
- `interaction_schema.yaml` に準拠した入出力オブジェクト
