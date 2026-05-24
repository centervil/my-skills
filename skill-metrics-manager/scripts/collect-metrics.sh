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

# Metrics Collection Script for Gemini CLI
# Orchestrator Refactored for Issue #10

OUTPUT_DIR=".ops/audit_logs"
OUTPUT_FILE="$OUTPUT_DIR/metrics.json"

mkdir -p "$OUTPUT_DIR"

COLLECTED_JSON="{}"

# Function to run collectors in a dir
run_collectors() {
    local DIR=$1
    if [ -d "$DIR" ]; then
        # Check if any .sh files exist
        count=$(ls "$DIR"/*.sh 2>/dev/null | wc -l)
        if [ "$count" != "0" ]; then
            for script in "$DIR"/*.sh; do
                if [ -x "$script" ]; then
                    log_info "Running collector: $script"
                    RESULT=$("$script")
                    if [ -z "$RESULT" ]; then RESULT="{}"; fi
                    # Merge result
                    COLLECTED_JSON=$(echo "$COLLECTED_JSON" "$RESULT" | jq -s '.[0] * .[1]')
                fi
            done
        fi
    fi
}

log_info "Collecting metrics..."

# Core Collectors
run_collectors "$(dirname "$0")/collectors"

# Project Specific Collectors
run_collectors ".ops/metrics/collectors"

# Aggregate and Save
FINAL_JSON=$(jq -n --arg time "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" --argjson metrics "$COLLECTED_JSON" '{timestamp: $time, metrics: $metrics}')

echo "$FINAL_JSON" > "$OUTPUT_FILE"
log_info "Metrics saved to $OUTPUT_FILE"