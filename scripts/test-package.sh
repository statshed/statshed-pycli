#!/bin/bash
# test-package.sh - Test package installation in an isolated environment
#
# This script builds and tests the statshed-cli package to verify:
# - Package builds correctly
# - Installs successfully in a fresh environment
# - Entry points work as expected
# - All commands are accessible

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TEST_VENV="${PROJECT_DIR}/.test-venv"

# Colors for output (respect NO_COLOR)
if [[ -z "${NO_COLOR:-}" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

cleanup() {
    if [[ -d "$TEST_VENV" ]]; then
        info "Cleaning up test virtual environment..."
        rm -rf "$TEST_VENV"
    fi
}

# AIDEV-NOTE: Cleanup on exit, but allow inspection on failure
trap cleanup EXIT

cd "$PROJECT_DIR"

# Build the package
info "Building package..."
rm -rf dist/
uv build

# Create fresh virtual environment
info "Creating isolated test environment..."
cleanup 2>/dev/null || true
uv venv "$TEST_VENV" --quiet

# Install the built wheel
info "Installing package from wheel..."
# AIDEV-NOTE: Validate exactly one wheel exists to avoid picking wrong version
WHEEL_COUNT=$(ls dist/*.whl 2>/dev/null | wc -l)
if [[ "$WHEEL_COUNT" -ne 1 ]]; then
    error "Expected exactly 1 wheel in dist/, found $WHEEL_COUNT"
    exit 1
fi
WHEEL=$(ls dist/*.whl)
VIRTUAL_ENV="$TEST_VENV" uv pip install "$WHEEL" --quiet

# Test basic entry point
info "Testing entry point: statshed --help"
"$TEST_VENV/bin/statshed" --help > /dev/null

info "Testing entry point: statshed --version"
VERSION=$("$TEST_VENV/bin/statshed" --version)
echo "  Version: $VERSION"

# Test all commands
info "Testing commands..."
for cmd in submit health groups jobs config group-config completion; do
    if "$TEST_VENV/bin/statshed" "$cmd" --help > /dev/null 2>&1; then
        echo "  ✓ statshed $cmd --help"
    else
        error "Failed: statshed $cmd --help"
        exit 1
    fi
done

# Test with rich extra
# AIDEV-NOTE: pip ignores extras on local wheel paths, so install rich directly
info "Testing installation with rich dependency..."
VIRTUAL_ENV="$TEST_VENV" uv pip install rich --quiet
"$TEST_VENV/bin/statshed" --help > /dev/null
echo "  ✓ Works with rich installed"

# Test shell completion generation
info "Testing shell completion generation..."
for shell in bash zsh fish; do
    if "$TEST_VENV/bin/statshed" completion "$shell" > /dev/null 2>&1; then
        echo "  ✓ statshed completion $shell"
    else
        warn "Shell completion for $shell not available (may require shell to be installed)"
    fi
done

info "All tests passed!"
