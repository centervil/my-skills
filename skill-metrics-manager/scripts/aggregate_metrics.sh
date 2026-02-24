#!/bin/bash

# Aggregate all metrics into .ops/audit_logs/metrics.json
# Path: .gemini/skills/skill-metrics-manager/scripts/aggregate_metrics.sh

METRICS_FILE=".ops/audit_logs/metrics.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

export COMPLIANCE_JSON=$(bash .ops/metrics/collectors/compliance.sh)
export AUTONOMY_JSON=$(bash .ops/metrics/collectors/autonomy.sh)

python3 - <<EOF
import json
import os

timestamp = "$TIMESTAMP"
compliance = json.loads(os.environ['COMPLIANCE_JSON'])
autonomy = json.loads(os.environ['AUTONOMY_JSON'])

result = {
    "timestamp": timestamp,
    "metrics": {
        **compliance,
        **autonomy
    }
}

with open('$METRICS_FILE', 'w') as f:
    json.dump(result, f, indent=2)
EOF

echo "Metrics aggregated to $METRICS_FILE"
