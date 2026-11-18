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

## Design & Architecture (新パイプライン仕様 - Issue #7)
- **新パイプラインの流れ**:
  1. **候補先行収集 (Session 1)**: 必要件数（`max_items`）に対し約2倍強（例: cybersecurity は 3件に対し 7件）の構造化候補リスト（タイトル、URL、公開日時、ソース名、スニペット）を収集。
  2. **機械的 Dedup (Python側)**: 対象日より前の直近7日分の既出レポートコーパスと照合し、URL完全一致・タイトル類似・主要キーワード一致の候補を除外。判定結果はメタデータに記録。
   3. **境界判定 (Session 1.5 またはバッチ)**: 機械判定で決めきれない候補を1セッションにバッチして「新事実あり／なし」を判定（**確定設定**: 2026-11-18 のユーザー判断に基づきデフォルトは `keep`）。
   4. **本文取得 (Python側)**: 残った候補のURLをHTTP GETで取得し本文テキスト（最大2,000文字）を抽出。失敗時はスニペットにフォールバック。
   5. **不足時再収集 (Session 1.8 - 条件付き最大1回)**: dedup後に必要件数へ足りない場合のみ、除外済みURLリストを除外対象としてクエリを変更し再収集を最大1回実施。なおも不足なら件数を減らして生成し `insufficient: true` を記録（**暫定設定**: デフォルトは `reduce`）。
  6. **本文ベース生成 (Session 2)**: 取得本文を基にテンプレート構造で記事化。
- **セッション会計**:
  - 1回の実行あたり agy セッション総数の上限は **最大4**（候補収集＋境界判定＋再収集＋生成）。実績（総セッション数、各usage）をメタデータ JSON に記録。
- **トークン予算レンジ (実測ベース)**:
  - 候補先行収集・バッチ判定・再収集・本文ベース生成を合わせた1回あたりの想定レンジ: **約 40k 〜 80k トークン**（#4 の実測 17.8k〜39.6k をベースに、プール拡大とDedup/境界判定追加を踏まえた新方式の規模）。
