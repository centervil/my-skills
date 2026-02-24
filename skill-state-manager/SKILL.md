---
name: skill-state-manager
description: プロジェクトの進捗状況（project_state.md やタスクリスト）を追跡し、自動的に同期・更新するスキル。
---

# Skill: 状態管理 (State Manager)

## 概要
プロジェクトの SSOT である `project_state.md` を常に最新の状態に保ち、コンテキストの整合性を維持する。

## Instructions
1. **進捗同期**: 各セッションの終了時に、完了したタスクと未完了のタスクを `project_state.md` に反映する。
2. **要約の生成**: 複雑な履歴を要約し、次のセッションの開始時に必要な「現在の状態」を明確にする。
3. **課題管理**: 新たに発生した課題や未解決の懸念点をリストに追加する。

## Output Contract
- 最新の `project_state.md`
- セッション間のコンテキスト要約
