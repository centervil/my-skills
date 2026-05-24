#!/bin/bash
set -euo pipefail

# Logging functions
log() {
    local level="$1"
    shift
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] [$level] $*"
}
log_info() { log "INFO" "$*"; }
log_error() { log "ERROR" "$*" >&2; }

ISSUE_ID=${1:-}
BRANCH_NAME=${2:-}

if [ -z "$ISSUE_ID" ] || [ -z "$BRANCH_NAME" ]; then
    log_error "Usage: $0 <issue-id> <branch-name>"
    exit 1
fi

log_info "Starting post-merge cleanup for Issue #$ISSUE_ID (Branch: $BRANCH_NAME)..."

# 1. Switch to main
git checkout main

# 2. Pull latest changes
git pull origin main

# 3. Delete the local issue branch
git branch -d "$BRANCH_NAME"

# 4. Sync submodules if any
git submodule update --init --recursive

log_info "Post-merge cleanup completed successfully."
