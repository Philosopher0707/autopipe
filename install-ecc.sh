#!/usr/bin/env bash
# Autopipe ECC Installer
# Copies .claude configs to ~/.claude/ (or target dir)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${1:-$HOME/.claude}"

if [[ ! -d "$REPO_ROOT/.claude" ]]; then
    echo "Error: .claude not found in repo root ($REPO_ROOT)"
    exit 1
fi

echo "Installing Autopipe ECC to $TARGET_DIR ..."
mkdir -p "$TARGET_DIR"

# Copy with rsync if available, else cp -r
if command -v rsync >/dev/null 2>&1; then
    rsync -a "$REPO_ROOT/.claude/" "$TARGET_DIR/"
else
    cp -r "$REPO_ROOT/.claude/"* "$TARGET_DIR/"
fi

echo "✅ Autopipe ECC installed to $TARGET_DIR"
echo ""
echo "Agents: python-pipeline-reviewer, frontend-reviewer, security-scanner"
echo "Skills:  tdd-python, pipeline-patterns, python-security"
echo "Rules:   common/coding-style, python/patterns, python/testing, ml-pipeline/config"
echo "Hooks:   session-start, post-edit-ruff, post-edit-mypy, suggest-compact"
echo ""
echo "Usage in Claude Code:"
echo "  /agent python-pipeline-reviewer"
echo "  /skill tdd-python"
echo "  /skill pipeline-patterns"
echo "  /security"
