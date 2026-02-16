---
name: skill-requirement-expert
description: ユーザーの抽象的な要望を具体化し、実装可能な要件定義（requirements.md）を作成する。
---

# Skill: Requirement Expert

## Overview
このスキルは、ユーザーとの対話を通じて「何を作りたいか」を詳細に定義します。IDD（Issue-Driven Development）プロセスの最初期段階（Phase: Start）において、品質のガードレールとして機能します。

## Capabilities
1. **Existing Issue Deep Dive**: 既存のIssueの内容を分析し、不足している情報をインタビューで補完します。
2. **New Issue Definition**: 新しい機能や修正の要望をゼロからインタビューし、要件をまとめます。

## Usage Guidelines

### 1. 引数（Issue ID）がある場合
1. `gh issue view [ID]` でIssueの詳細を取得します。
2. 背景、利用シーン、期待される成果物、完了定義の4つの観点で不足している情報を特定します。
3. ユーザーに1つずつ質問を行い、回答を深掘りします。
4. 全ての情報を統合し、`docs/issues/[ID]/requirements.md` を作成または更新します。

### 2. 引数がない場合
1. 「どのような機能や改善を検討されていますか？」という問いかけからスタートします。
2. 以下の項目を対話形式で埋めていきます。
   - **Background**: なぜそれが必要か。
   - **User Story**: 誰が、いつ、どのように使うか。
   - **Success Criteria**: どのような状態になれば「完了」か。
3. 情報を `docs/issues/draft/requirements.md` (一時保存) にまとめ、ユーザーの承認を得ます。
4. 承認後、`gh issue create` のための情報を整理して提示します。

## Interview Rules
- 一度に全ての質問を投げず、チャットの特性を活かして1つずつ丁寧に深掘りしてください。
- ユーザーが「おまかせ」と言った場合でも、プロジェクトの `AGENTS.md` や既存アーキテクチャに基づいた「最適な提案」を行い、承認を得る形で進めてください。
