---
name: skill-web-collection
description: Antigravity CLIを用いた汎用Web収集、機械的重複除去（dedup）、本文ベース生成、再収集パイプラインスキル。
---

# Skill: 汎用 Web 収集・記事生成 (Web Collection with Dedup Pipeline)

## Definition / Overview
このSkillは、Antigravity CLI (`agy`) を用いて、収集プロファイル（テーマ、対象期間、ソース制約、件数上限、dedup設定など）と出力テンプレートに基づいた Web の候補先行収集、機械的 dedup（重複除去）、バッチ境界判定、本文取得、不足時再収集、および構造化記事の生成を行います。

## Usage Guidelines (Instructions)
AI がこの Skill を使用する際は、以下の手順に従ってください。

1. **過去の知見の確認**:
   `references/known_issues.md` を読み込み、過去の制限事項やエラー対策を確認する。

2. **プロファイルと対象日の確認**:
   - 収集プロファイル JSON（テーマ、件数上限、dedup設定、テンプレートパスなど）を確認・用意する。
     - `dedup`: 既出レポートの格納ディレクトリ (`reports_dir`) と直近照合日数 (`days`, 既定7日) を指定。対象日より前のレポートをコーパスとして参照します。
      - `boundary_default`: 境界判定が不確実な場合の既定動作（**確定**: 2026-11-18 のユーザー判断により `keep`＝候補に入れる。理由は何度も違うソースで拾われるものは重要かもしれないし、前日に聞き逃がしている可能性があるため）。
      - `insufficient_fallback`: 候補不足時の既定動作（**暫定**: `reduce`＝件数を減らして公開＋insufficientフラグ記録）。
     - `template_path`: 相対パス指定時はプロファイルJSON位置基準で自動解決。
   - 対象日（`YYYY-MM-DD`）を呼び出し側が明示的に指定する。
   - `constraints.max_items` は必須指定。

3. **ラッパースクリプトの実行**:
   ```bash
   python3 scripts/agy-collect-wrapper.py \
     --profile profiles/cybersecurity_news.json \
     --target-date YYYY-MM-DD \
     --output output_article.md \
     --metadata-output metadata.json
   ```

4. **エラーハンドリング契約**:
   - `RATE_LIMITED`: 429 / RESOURCE_EXHAUSTED / quota 制限。再試行せず停止。
   - `AUTH_REQUIRED`: 認証切れ。
   - `FAILED`: その他エラー。

## Design & Architecture (新パイプライン仕様 - Issue #7 & #9)
- **新パイプラインの流れ (Issue #9 更新版)**:
  1. **候補先行収集 (Session 1)**: 必要件数（`max_items`）に対し約2倍強（例: cybersecurity は 3件に対し 7件）の構造化候補リストを収集。
  2. **機械的 Dedup (Python側)**: 直近レポートコーパスと照合し、重複を除外。
  3. **取得可能性判定 (Python側)**: 機械的 dedup の生存候補に対し本文取得（第一段 HTTP 2xx 且つ文字数 ≥ `fetchable_min_chars` 既定600）を試行。失敗が 403 でプロファイル `browser_fallback` 有効時は第二段（Playwright 実ブラウザ遅延読み込み）を試行（非対応環境では自動無効化）。404 は対象外。判定結果（`fetchable`, `fetch_reason`, `fetch_status`, `body_source`, `body_length`）をメタデータに記録。取得本文はキャッシュ。
  4. **再収集の条件拡張 (Session 1.8 - 条件付き最大1回)**: 取得可能件数 < max_items の場合（従来の dedup 後不足も含む）に再収集を発動。上限は追加1回まで。再収集では既見の全 URL を除外。
  5. **境界判定 (Session 1.5 - 再収集の後)**: 再収集の後に1回だけ最終プールへ実施し、セッション総数上限4を維持（デフォルト keep）。
  6. **選別と insufficient**: `fetchable` な候補を優先して `max_items` まで選別。不足分はスニペット項目で補充し `snippet_only: true` を明示。選別された fetchable が max_items 未満の場合は `insufficient: true` とし理由を記録（公開は止めない）。
  7. **本文ベース生成 (Session 2)**: 取得済み本文・スニペットを基に記事化。メタデータにサマリ（`candidates_total`, `fetchable_count`, 取得可能率, 再収集の発動有無, 最終構成）を追加。
- **セッション会計**:
  - 1回の実行あたり agy セッション総数の上限は **最大4**。実績をメタデータ JSON に記録。
- **トークン予算レンジ (実測ベース)**:
  - 候補先行収集・バッチ判定・再収集・本文ベース生成を合わせた1回あたりの想定レンジ: **約 40k 〜 80k トークン**（#4 の実測 17.8k〜39.6k をベースに、プール拡大とDedup/境界判定追加を踏まえた新方式の規模）。
