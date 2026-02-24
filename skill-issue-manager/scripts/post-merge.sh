#!/bin/bash
# post-merge.sh: Automate cleanup after PR merge.

ISSUE_ID=$1
BRANCH_NAME=$2

if [ -z "$ISSUE_ID" ] || [ -z "$BRANCH_NAME" ]; then
    echo "Usage: $0 <issue-id> <branch-name>"
    exit 1
fi

echo "Starting post-merge cleanup for Issue #$ISSUE_ID (Branch: $BRANCH_NAME)..."

# 1. Switch to main
git checkout main

# 2. Pull latest changes
git pull origin main

# 3. Delete the local issue branch
git branch -d "$BRANCH_NAME"

# 4. Sync submodules if any
git submodule update --init --recursive

# 5. Push submodules if they have local changes (already merged in PR but for safety)
# git submodule foreach 'git push origin main || true'

echo "Post-merge cleanup completed successfully."
