---
name: skill-project-and-skill-architect
description: プロジェクトの構成要素（README.md, AGENTS.md）の構築・修正や、新しいSkill（ツール）の設計・開発を行う際に使用する、基盤エンジニアリングスキル。
---

# Skill: システム設計・基盤構築 (Architect)

## 概要
プロジェクトの基盤構成（README/AGENTS）の設計・更新、および Skill（機能モジュール）の新規設計・開発を担う。

## Instructions
1. **基盤設計**: `README.md` と `AGENTS.md` の役割分担、およびプロジェクト全体の物理構造を設計する。
2. **Skill 開発**: 必要な機能を Skill として設計し、テンプレート（`skill-definition.md`）に従って実装する。
3. **モード定義**: 各 Mode の役割と入出力契約（`00-contract.md`）を策定する。
4. **テンプレート管理**: `.ops/templates/` 配下の最新テンプレート構造を維持し、全成果物に適用する。

## Output Contract
- 新規・更新された Skill (SKILL.md, scripts/, etc.)
- プロジェクト基盤の定義ファイル (README.md, AGENTS.md, etc.)
- `interaction_schema.yaml` に準拠したモード定義
