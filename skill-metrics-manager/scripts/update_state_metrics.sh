#!/bin/bash

# Update project_state.md with latest metrics from metrics.json
# Path: .gemini/skills/skill-metrics-manager/scripts/update_state_metrics.sh

METRICS_FILE=".ops/audit_logs/metrics.json"
STATE_FILE=".ops/project_state.md"

if [ ! -f "$METRICS_FILE" ]; then
    echo "Metrics file not found."
    exit 1
fi

# Extract values using python for reliability
VALUES=$(python3 - <<EOF
import json
with open('$METRICS_FILE') as f:
    data = json.load(f)
    m = data['metrics']
    comp = m.get('compliance', {})
    auto = m.get('autonomy', {})
    score = comp.get('score', 0)
    fidelity = comp.get('protocol_fidelity', 0)
    alignment = comp.get('behavioral_alignment', 0)
    rate = auto.get('rate', 0)
    print(f"{score}|{fidelity}|{alignment}|{rate}")
EOF
)

IFS='|' read -r SCORE FIDELITY ALIGNMENT AUTO_RATE <<< "$VALUES"

export SCORE FIDELITY ALIGNMENT AUTO_RATE

python3 - <<EOF
import re
import os

with open('$STATE_FILE', 'r') as f:
    content = f.read()

score = os.environ['SCORE']
fidelity = float(os.environ['FIDELITY']) * 100
alignment = float(os.environ['ALIGNMENT']) * 100
auto_rate = float(os.environ['AUTO_RATE']) * 100

metrics_section = f"""## Metrics (Snapshot)
- **System Integrity (Dynamic)**:
    - Protocol Fidelity: {fidelity:.1f}%
    - Behavioral Alignment: {alignment:.1f}%
    - Overall Compliance Score: {score}
- **Autonomy Rate**: {auto_rate:.1f}%
"""

# Replace existing metrics section or append if not found
if "## Metrics" in content:
    new_content = re.sub(r"## Metrics \(Snapshot\).*?(?=\n##|$)", metrics_section, content, flags=re.DOTALL)
else:
    new_content = content + "\n" + metrics_section

with open('$STATE_FILE', 'w') as f:
    f.write(new_content)
EOF

echo "project_state.md updated with latest metrics."
