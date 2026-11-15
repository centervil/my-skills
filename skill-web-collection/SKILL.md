# Skill: 汎用 Web 収集・記事生成 (Web Collection)

## Definition / Overview
このSkillは、Antigravity CLI (`agy`) を用いて、収集プロファイル（テーマ、対象期間、ソース制約、件数上限、モデル指定など）と出力テンプレートに基づいた Web 収集および構造化記事の生成を行います。ニュース専用にせず、任意のテーマとテンプレートで再利用可能な形で設計されています。

## Usage Guidelines (Instructions)
AI がこの Skill を使用する際は、以下の手順に従ってください。

1. **過去の知見の確認**:
   `references/known_issues.md` を読み込み、過去の制限事項やエラー対策を確認する。

2. **プロファイルと対象日の確認**:
   - 収集プロファイル JSON（テーマ、件数上限、テンプレートパスなど）を確認・用意する。
   - 対象日（`YYYY-MM-DD`）を呼び出し側が明示的に指定する（今日起点の推論を行わない）。

3. **ラッパースクリプトの実行**:
   `scripts/agy-collect-wrapper.py` を以下のコマンドで実行する:
   ```bash
   python3 scripts/agy-collect-wrapper.py \
     --profile profiles/cybersecurity_news.json \
     --target-date YYYY-MM-DD \
     --output output_article.md \
     --metadata-output metadata.json
   ```

4. **エラーハンドリング契約**:
   ラッパーは終了コードおよび出力メタデータの `status` に従ってエラーを分類する。
   - `RATE_LIMITED`: 429 / RESOURCE_EXHAUSTED / quota 制限。再試行せず停止（必要に応じ NotebookLM 等への縮退を判断）。
   - `AUTH_REQUIRED`: 認証切れ。最悪時以外は再試行せず報告。
   - `FAILED`: その他エラー。

## Design & Architecture (設計記録)
- **スキル名の理由**: 特定のニュースドメイン（例: ニュースキュレーション専用）に固定せず、任意のプロファイル（テーマ、対象期間、件数上限、モデル、出力テンプレート）を指定して汎用的に Web 収集・構造化記事生成を行えるため、`skill-web-collection` と命名。
- **プロファイルスキーマ (`profiles/*.json`)**:
  - `theme`: 収集テーマ
  - `sources`: 信頼するソースや収集元のガイドラインの配列
  - `constraints`: `max_items`（最大件数上限）, `time_window`
  - `model`: 使用する AI モデル（既定: `gemini-3.8-flash-low`）
  - `effort`: 推論エフォートレベル
  - `template_path`: 出力フォーマットを指定する Markdown テンプレートへのパス
- **入出力契約 (Input/Output Contract)**:
  - **入力**: プロファイル JSON、対象日（`YYYY-MM-DD`）
  - **出力**: 構造化済み Markdown 記事、実行メタデータ JSON（`status`, `target_date`, `profile`, `model`, `usage` 等を含む）
- **エラー分類**:
  - `RATE_LIMITED`: 429 / RESOURCE_EXHAUSTED / quota 制限。再試行せず停止（必要に応じ NotebookLM 等への縮退を判断）。
  - `AUTH_REQUIRED`: 認証切れ。最悪時以外は再試行せず報告。
  - `FAILED`: その他エラー。
- **検証計画・結果**:
  - 対象日 `2026-11-14` を指定し、`cybersecurity_news.json` プロファイルおよび対応テンプレートを用いてラッパーを実行。
  - セッション 1（収集: usage token 合計 ~39,648）および セッション 2（記事生成: usage token 合計 ~15,419）がともに `status: "OK"` で完了し、テンプレートの全セクション構造（主要ポイント、カテゴリ別要約、詳細、深掘り、結論、主要引用）に完全に準拠した高品質な記事が出力されることを実証済み。
- **ラッパースクリプト**: `scripts/agy-collect-wrapper.py`
- **サンプルプロファイル**: `profiles/`
- **知見蓄積**: `references/known_issues.md`
