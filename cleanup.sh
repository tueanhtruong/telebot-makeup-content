#!/bin/bash

# TeleNotiApp - Python Cleanup Script
# Removes .venv, __pycache__, and .pyc files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Python Cleanup Utility                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Show what will be removed
echo -e "${YELLOW}📊 Scanning for files to remove...${NC}"
echo ""

# Count items
VENV_SIZE=$(du -sh "$SCRIPT_DIR/.venv" 2>/dev/null || echo "0B")
PYCACHE_COUNT=$(find "$SCRIPT_DIR" -type d -name "__pycache__" 2>/dev/null | wc -l)
PYC_COUNT=$(find "$SCRIPT_DIR" -type f -name "*.pyc" 2>/dev/null | wc -l)

echo -e "${YELLOW}.venv directory:${NC}"
if [ -d "$SCRIPT_DIR/.venv" ]; then
    echo "  Size: $VENV_SIZE"
    echo "  Path: $SCRIPT_DIR/.venv"
else
    echo "  Not found"
fi

echo ""
echo -e "${YELLOW}__pycache__ directories:${NC}"
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    echo "  Found: $PYCACHE_COUNT directories"
else
    echo "  None found"
fi

echo ""
echo -e "${YELLOW}.pyc files:${NC}"
if [ "$PYC_COUNT" -gt 0 ]; then
    echo "  Found: $PYC_COUNT files"
else
    echo "  None found"
fi

echo ""
echo "────────────────────────────────────────────"
echo ""

# Ask for confirmation
read -p "$(echo -e ${YELLOW}Continue with cleanup? \(y/n\)${NC} )" -n 1 -r
echo
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    echo ""

    # Remove .venv
    if [ -d "$SCRIPT_DIR/.venv" ]; then
        echo -e "${BLUE}  Removing .venv...${NC}"
        rm -rf "$SCRIPT_DIR/.venv"
        echo -e "${GREEN}  ✓ .venv removed${NC}"
    fi

    # Remove __pycache__ directories
    REMOVED_DIRS=$(find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null | wc -l || echo 0)
    if [ "$PYCACHE_COUNT" -gt 0 ]; then
        echo -e "${BLUE}  Removing __pycache__ directories...${NC}"
        find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        echo -e "${GREEN}  ✓ $PYCACHE_COUNT __pycache__ directories removed${NC}"
    fi

    # Remove .pyc files
    if [ "$PYC_COUNT" -gt 0 ]; then
        echo -e "${BLUE}  Removing .pyc files...${NC}"
        find "$SCRIPT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
        echo -e "${GREEN}  ✓ $PYC_COUNT .pyc files removed${NC}"
    fi

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Cleanup Complete!                  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "You can now recreate the virtual environment with:"
    echo -e "${BLUE}  python3 -m venv .venv${NC}"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
else
    echo -e "${YELLOW}⚠️  Cleanup cancelled${NC}"
    exit 0
fi
