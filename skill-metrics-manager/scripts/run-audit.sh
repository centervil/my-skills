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

# 1. Run the core metrics collection
log_info "Running metrics collection..."
"$(dirname "$0")/collect-metrics.sh"

METRICS_FILE=".ops/audit_logs/metrics.json"
HISTORY_DIR=".ops/audit_logs/history"

if [ ! -f "$METRICS_FILE" ]; then
  log_error "Metrics file was not generated."
  exit 1
fi

# 2. Archive with timestamp
mkdir -p "$HISTORY_DIR"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
HISTORY_FILE="$HISTORY_DIR/metrics_$TIMESTAMP.json"

cp "$METRICS_FILE" "$HISTORY_FILE"

log_info "Metrics archived to: $HISTORY_FILE"

# 3. Check Quality Gates if --check is provided
if [[ "$*" == *"--check"* ]]; then
  python3 "$(dirname "$0")/check-gates.py"
  GATE_EXIT_CODE=$?
else
  GATE_EXIT_CODE=0
fi

# 4. Display summary (requires jq)
if command -v jq >/dev/null 2>&1; then
  log_info ""
  log_info "--- Current Status ---"
  jq .metrics "$METRICS_FILE"
else
  log_info ""
  log_info "Tip: Install 'jq' for better visualization."
fi

exit $GATE_EXIT_CODE
