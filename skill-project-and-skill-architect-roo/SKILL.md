---
name: skill-project-and-skill-architect-roo
description: プロジェクトの構成要素（README.md, AGENTS.md）の構築・修正や、新しいSkill（ツール）の設計・開発を行う際に使用する、基盤エンジニアリングスキル。
---

# Skill: システム設計・基盤構築 (Architect)

## 概要
プロジェクトの基盤構成（README/AGENTS）の設計・更新、および Skill（機能モジュール）の新規設計・開発を担う。

## Instructions
1. **基盤設計**: `README.md` と `AGENTS.md` の役割分担、およびプロジェクト全体の物理構造を設計する。
2. **Skill 開発**: 必要な機能を Skill として設計し、以下の「自己改善ループ」を組み込んで実装する。
    - **知見蓄積ファイルの作成**: `references/known_issues.md` を必ず作成し、知見を蓄積可能な状態にする。
    - **自己改善プロンプトの挿入**: 生成する `SKILL.md` のワークフローの冒頭（Step 1 等）に、必ず `known_issues.md` を読み込んで過去の知見を確認する指示を追加する。
    - テンプレート（`skill-definition.md`）が存在する場合はそれに従い、存在しない場合は標準的な構造（SKILL.md, scripts/, references/）を採用する。
3. **モード定義**: 各 Mode の役割と入出力契約（`00-contract.md`）を策定する。
4. **テンプレート管理**: `.ops/templates/` 配下の最新テンプレート構造を維持し、全成果物に適用する。

## Output Contract
- 新規・更新された Skill (SKILL.md, scripts/, etc.)
- プロジェクト基盤の定義ファイル (README.md, AGENTS.md, etc.)
- `interaction_schema.yaml` に準拠したモード定義
