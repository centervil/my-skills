---
name: skill-metrics-manager
description: プロジェクトのメトリクス収集（監査の実行、新規メトリクスの作成、ステータス分析）を管理するスキル。
---

# Skill: メトリクス管理 (Metrics Manager)

## 概要
プロジェクトの自律性、規約遵守率、作業効率を定量的に計測し、進捗状況を可視化する。

## Instructions
1. **メトリクス収集**: `.ops/metrics/collectors/` 配下のスクリプトを実行し、データを収集する。
2. **監査証跡の集計**: `aggregate_metrics.sh` を実行し、`.ops/audit_logs/sessions/` 内のデータを集計して `.ops/audit_logs/metrics.json` を更新する。
3. **ステータス分析**: `metrics.yaml` の閾値と比較し、プロジェクトの健全性を評価する。
4. **ダッシュボード更新**: `update_state_metrics.sh` を実行し、`project_state.md` に最新のメトリクス結果を反映する。

## Procedure
1.  **集計実行**: `bash .gemini/skills/skill-metrics-manager/scripts/aggregate_metrics.sh` を実行する。
2.  **可視化反映**: `bash .gemini/skills/skill-metrics-manager/scripts/update_state_metrics.sh` を実行する。
3.  **分析報告**: 更新された `metrics.json` の内容を要約し、ユーザーに報告する。

## Output Contract
- 更新された `metrics.json` および `project_state.md`
- プロジェクトの健全性に関する分析レポート
