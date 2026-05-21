#!/bin/bash

# Project Setup Script for Roocode
# Usage: ./setup-project.sh "PROJECT_NAME" "PROJECT_DESCRIPTION" "TARGET_DIR"

PROJECT_NAME="$1"
PROJECT_DESCRIPTION="$2"
TARGET_DIR="${3:-.}"

# Pre-defined source paths (relative to repo root)
SRC_OPS=".ops"

# Error handling
if [ -z "$PROJECT_NAME" ] || [ -z "$PROJECT_DESCRIPTION" ]; then
    echo "Error: Project Name and Description are required."
    exit 1
fi

echo "Setting up project '$PROJECT_NAME' in '$TARGET_DIR'..."

# Create core directories
mkdir -p "$TARGET_DIR"/.ops/{metrics/collectors,policies,scripts,templates/{logs,system,work-artifacts}}
mkdir -p "$TARGET_DIR"/{docs/issues,development_logs}

# Copy essential templates and configurations
cp -r "$SRC_OPS"/templates/work-artifacts/* "$TARGET_DIR"/.ops/templates/work-artifacts/ 2>/dev/null

# Backup existing files
if [ -f "$TARGET_DIR/README.md" ]; then
    echo "Backing up existing README.md to README.old.md"
    mv "$TARGET_DIR/README.md" "$TARGET_DIR/README.old.md"
fi
if [ -f "$TARGET_DIR/AGENTS.md" ]; then
    echo "Backing up existing AGENTS.md to AGENTS.old.md"
    mv "$TARGET_DIR/AGENTS.md" "$TARGET_DIR/AGENTS.old.md"
fi

# .ops/project_state.md (initial)
cat <<'EOF' > "$TARGET_DIR"/.ops/project_state.md
# Project State: {{PROJECT_NAME}}

## Overview
{{PROJECT_DESCRIPTION}}

## Status
- [x] Project Set up
- [ ] Requirements Defined
- [ ] Implementation Started

## Next Steps
1. Define the first Issue and start IDD workflow.
EOF

# AGENTS.md (Constitutional core - Principles only)
cat <<'EOF' > "$TARGET_DIR"/AGENTS.md
# AI Agents Operational Principles

This file defines the fundamental behavioral principles for AI agents in **{{PROJECT_NAME}}**.

## 1. Core Identity
You are an autonomous developer and system operator for **{{PROJECT_NAME}}**. Your goal is to maintain the integrity of the system while evolving its capabilities through a disciplined development process.

## 2. Behavioral Principles
- **Issue-Centricity (IDD)**: Every modification must originate from a defined Issue. All work (specifications, designs, implementations, and logs) must be contained within the designated issue workspace.
- **Architectural Separation**:
    - **Common Infrastructure**: Maintain reusable, project-agnostic assets with high portability.
    - **Project Operations**: Manage project-specific data, logs, and local logic without contaminating the shared infrastructure.
- **Verification First**: Always verify changes through tests and standards before finalizing.

## 3. Operational Rules
The specific procedures for development (IDD lifecycle, testing, etc.) are defined in the project's **README.md** and specialized **Skills**. Adhere to those protocols for task execution.
EOF

# README.md (Project Map)
cat <<'EOF' > "$TARGET_DIR"/README.md
# {{PROJECT_NAME}}

{{PROJECT_DESCRIPTION}}

## Directory Structure
- `.gemini/`: Common Infrastructure for Gemini CLI.
- `.roo/`: Common Infrastructure for Roo Code (Cline).
- `.ops/`: Project-Specific Operations (logs, metrics, templates).
- `docs/issues/`: Issue-specific documentation (IDD).
- `development_logs/`: Daily development logs.

## Operational Protocols
| Concept | Physical Path | Description |
| :--- | :--- | :--- |
| Project State | `.ops/project_state.md` | Current project status and next steps. |
| Issues | `docs/issues/` | Issue-specific requirements, design, and tasks. |
| Logs | `development_logs/` | Daily records of development activities. |
| Skills | `.gemini/skills/` | Specialized capabilities for the agent. |
| Slash Command Policy | `docs/policies/slash-commands.md` | Policy for defining slash commands. |

## Getting Started
Run `/help` to see available commands.
EOF

# Replace placeholders
sed -i "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$TARGET_DIR"/.ops/project_state.md
sed -i "s/{{PROJECT_DESCRIPTION}}/$PROJECT_DESCRIPTION/g" "$TARGET_DIR"/.ops/project_state.md
sed -i "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$TARGET_DIR"/AGENTS.md
sed -i "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" "$TARGET_DIR"/README.md
sed -i "s/{{PROJECT_DESCRIPTION}}/$PROJECT_DESCRIPTION/g" "$TARGET_DIR"/README.md

echo "Project '$PROJECT_NAME' set up successfully in '$TARGET_DIR'."
