---
name: skill-metrics-manager
description: プロジェクトのメトリクス収集（監査の実行、新規メトリクスの作成、ステータス分析）を管理するスキル。
---

# Skill: メトリクス管理 (Metrics Manager)

## 概要
プロジェクトの自律性、規約遵守率、作業効率を定量的に計測し、進捗状況を可視化する。

## Instructions
1. **メトリクス収集**: `.ops/metrics/collectors/` 配下のスクリプトを実行し、データを収集する。
2. **監査履歴の記録**: 収集結果を `.ops/audit_logs/metrics.json` に統合・記録する。
3. **ステータス分析**: `metrics.yaml` の閾値と比較し、プロジェクトの健全性を評価する。
4. **ダッシュボード更新**: `project_state.md` に最新のメトリクス結果を反映する。

## Output Contract
- 更新された `metrics.json` および `project_state.md`
- プロジェクトの健全性に関する分析レポート
