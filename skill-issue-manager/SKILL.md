---
name: skill-issue-manager
description: GitHub Issueのライフサイクル管理（作成、仕様策定、実装、レビュー、完了）を自動化・支援し、Issue駆動開発（IDD）を推進するスキル。
---

# Skill: GitHub Issue Manager

GitHub Issueのライフサイクル全体（作成、開発開始、実装、レビュー、完了）を管理し、Issue駆動開発（IDD）のプロセスを自動化・支援します。

## Capabilities

1.  **Create Issue**: ユーザーの要望に基づき、適切なテンプレートとラベルを使用して新規Issueを作成します。
2.  **Manage Development Cycle**: 既存のIssueに対し、仕様策定(Start) -> 実装(Task) -> レビュー(Review) -> 完了(End) の一連のフローを実行します。

---

## Usage Guidelines

このスキルは開発プロセスを定義しますが、具体的な技術スタック（テストコマンド、リンター、ディレクトリ構成、ブランチ命名規則等）については、必ず **`AGENTS.md`** を参照して、プロジェクト固有のルールに従ってください。

### 1. Create Issue (新規Issue作成)

ユーザーから要望があった際、プロジェクトのテンプレート（`.github/ISSUE_TEMPLATE/` 等）に基づき、分類、下書き作成、ユーザー確認を経てIssueを作成します。

---

### 2. Manage Development Cycle (IDDワークフロー)

#### A. 開発開始 (Phase: Start)

1.  **ブランチ確認と作成 (Mandatory Gate)**:
    *   現在のブランチ (`git branch --show-current`) を確認します。
    *   `main` ブランチにいる場合は、必ず Issue 専用の作業ブランチ (例: `issue-[ID]`, `feat/[ID]`) を作成して切り替えてください。**`main` での直接作業は厳禁です。**

2.  **Issue の読み込みと要件確認 (Requirements Retrieval)**:
    *   `gh issue view [ID]` でIssueの詳細（Body）を取得します。
    *   **SSOT 準拠**: 要件は GitHub Issue の Body に記載されているものを正文（SSOT）として扱います。
    *   **粒度評価 (Assessment)**: `README.md` の「Issue 粒度の基準」に照らし、対象 Issue の範囲（Scope）が適切か評価してください。
    *   もし GitHub の Body に要件（Background, Goals, Success Criteria 等）が不足している場合は、実装を開始する前に `requirements` コマンドで要件を固めるようユーザーに促してください。`dev` コマンド内での要件定義インタビューは原則として行いません。

3.  **仕様ドキュメント生成と自律的移行 (Phase Gate)**:
    *   GitHub の Body に基づき、`design.md` および `tasks.md` を作成します。
    *   **自律的移行**: GitHub Issue の Body に詳細な要件（Background, Goals, Success Criteria 等）が揃っている場合、または `skill-requirement-expert` を経由している場合は、**`tasks.md` の承認を待たずに即座に `Task` フェーズ（実装）へ移行してください。**
    *   要件が不明確な場合のみ、ユーザーに提示して承認を得てください。

#### B. タスク実行 (Phase: Task)

1.  **実装ループ**:
    *   作成された `tasks.md` に従い、順次実装します。
    *   **自律的完遂**: `Task` 開始後は、`Review`、`End` (PR作成) までを自律的に完遂してください。
    *   **検証**: 各タスク完了後にテストやリンターを実行し、品質を確保してください。

2.  **トレーサビリティ (セッションログ)**:
    *   各セッションの終了時（または主要な区切り）に、`development_logs/YYYY-MM-DD-issue-[ID]-session-[N].md` を作成し、実施内容と技術詳細を記録してください。

#### C. 品質レビュー (Phase: Review)

1.  **自己レビュー**:
    *   変更内容が要件を満たし、`AGENTS.md` の憲章（原則）に合致しているか確認します。
    *   **アーキテクチャ監査**:
        - **レイヤー分離**: 共通基盤がプロジェクト固有領域（`.ops`）に依存していないか。
        - **ポータビリティ**: 成果物がプロジェクト間で再利用可能な構造になっているか。

#### D. 開発終了 (Phase: End)

1.  **最終検証**:
    *   プロジェクト全体のテスト・ビルドコマンドを実行し、不整合がないことを確認します。

2.  **記録と統合 (Wait for Human Review)**:
    *   PR (Pull Request) を作成し、成果物を報告します。
    *   **PR 承認待ち**: ユーザーに PR の内容を提示し、マージの承認（Approve）を待ってください。

#### E. マージと環境同期 (Phase: Merge/Sync)

1.  **自律的マージ**:
    *   PR が承認された後、自律的に PR をマージし、作業ブランチを削除してください。
    *   **サブモジュール同期**: 変更にサブモジュールが含まれる場合、必ずサブモジュールのリモートへ Push してください。

2.  **ローカル環境の更新**:
    *   `main` ブランチに戻り、`git pull` および `git submodule update` を実行して、最新の状態をローカルに反映させてください。
    *   この同期が完了した時点で、Issue セッションを終了とします。

---

## Resources
- **Guidelines**: `AGENTS.md` (プロジェクト固有の「正解」が記述されたソース。スクリプトパスや手順はここを参照)
