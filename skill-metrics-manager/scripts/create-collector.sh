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

# Usage: ./create-collector.sh [filename_without_extension]
# Example: ./create-collector.sh check_todos

NAME=$1
if [ -z "$NAME" ]; then
  log_error "Filename argument is required."
  log_error "Usage: $0 [filename_without_extension]"
  exit 1
fi

TARGET_DIR=".ops/metrics/collectors"
TARGET_FILE="$TARGET_DIR/$NAME.sh"
TEMPLATE="skills/skill-metrics-manager/references/collector-template.sh"

mkdir -p "$TARGET_DIR"

if [ -f "$TARGET_FILE" ]; then
  log_error "File $TARGET_FILE already exists."
  exit 1
fi

cp "$TEMPLATE" "$TARGET_FILE"
chmod +x "$TARGET_FILE"

log_info "Success: Created new collector at $TARGET_FILE"
log_info "Please edit the file to implement your specific measurement logic."
