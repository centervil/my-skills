---
name: skill-name-id
description: Brief description of the skill (one sentence).
---

# Skill: [Display Name]

## Definition / Overview
このSkillは、[目的] を達成するための専門的なワークフローと知見を提供します。

## Usage Guidelines (Instructions)
AIはこのSkillを使用する際、以下の手順に厳密に従ってください。

1. **過去の知見の確認**:
   `.gemini/skills/[skill-name-id]/references/known_issues.md` を `read_file` で読み込み、過去に発生した問題、失敗、または注意点を確認してください。

2. **[手順 1]**:
   ...

3. **[手順 2]**:
   ...

## 自己改善ループ
このSkillの使用中にエラーや想定外の挙動が発生した場合は、必ず原因を分析し、`.gemini/skills/[skill-name-id]/references/known_issues.md` に以下の形式で記録してください。

### [問題の概要]
- **発生日**: YYYY-MM-DD
- **症状**: 何が起きたか
- **原因**: なぜ起きたか
- **対策**: どう解決したか / 今後どう防ぐか

## Resources
- **知見蓄積ファイル**: `.gemini/skills/[skill-name-id]/references/known_issues.md`
- **その他**: ...
