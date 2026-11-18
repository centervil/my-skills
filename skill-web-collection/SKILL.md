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

## Design & Architecture (新パイプライン仕様 - Issue #7, #9, #12 RSS優先化)
- **フィード登録ファイル (`cybersecurity_feeds.json`) と可変管理 (Issue #12)**:
  - 置き場所: `skill-web-collection/profiles/cybersecurity_feeds.json`（プロファイル `cybersecurity_news.json` から `"feeds_file": "cybersecurity_feeds.json"` で相対参照）。
  - 項目: `id`（識別子）, `name`（名称）, `url`（フィードURL）, `region` (`domestic` / `overseas`), `type` (`public` / `media` / `blog` 等), `enabled` (真偽), `notes`（備考）。
  - **フィード追加手順**: コード変更は一切不要。`cybersecurity_feeds.json` に新しいフィードのエントリを1つ追加し、`enabled: true` に設定の上、単体テストを実行して妥当性を確認するだけで完了します。
- **RSS 優先フローの流れ (Issue #12 更新版)**:
  1. **RSS プール収集 (非LLM・決定スクリプト `rss_collect.py`)**: `feeds_file` があるプロファイルでは、まず指定された RSS / Atom フィード群から対象日の JST 暦日 `[00:00, 24:00)` のアイテムを抽出し、候補リスト（`origin: "rss"`）を作成。フィードごとの失敗はスキップして記録。
  2. **機械的 Dedup (Python側)**: 直近レポートコーパスと照合し重複を除外。
  3. **取得可能性判定 (Python側)**: 生存候補に対し HTTP 本文取得可能性（HTTP 2xx 且つ文字数 ≥ `fetchable_min_chars`）を判定。
  4. **agy 補充 (条件付き最大1回)**: fetchable な候補数が `max_items` 未満の場合のみ、従来の agy Web 検索を用いた再収集で不足分を補充（既見 URL 除外、補充候補には `origin: "agy"` を付与）。十分な場合は agy 検索セッションをスキップ。
  5. **境界判定 (Session 1.5)**: 必要に応じて1回実施。
  6. **選別・本文ベース生成**: 記事生成。メタデータにフィード別結果、由来内訳（RSS由来 / agy補充）を記録。
- **セッション会計**:
  - RSS 優先化により、1回の実行あたりの agy セッション総数の上限は **最大3**（補充 1 ＋ 境界 1 ＋ 生成 1）に削減（RSSが十分な場合は最大2）。
- **トークン予算レンジ (実測ベース)**:
  - 効率化により、LLM 呼び出しを最小限に抑えつつ安定したニュース収集を実現。
