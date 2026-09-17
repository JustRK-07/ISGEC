#!/bin/bash
# run.sh — one-shot driver for Approach C (1-block overlay)
#
# Runs: scripts/clean.py → scripts/fit.py → scripts/overlay.py
# Output: out/TP-104 OVERLAY_C.dxf
set -e

cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════════════════════"
echo "  Approach C — 1-block overlay"
echo "═══════════════════════════════════════════════════════════════"

echo
echo "── Step 1/3: CLEAN ──"
python3 scripts/clean.py

echo
echo "── Step 2/3: FIT ──"
python3 scripts/fit.py

echo
echo "── Step 3/3: OVERLAY ──"
python3 scripts/overlay.py

echo
echo "═══════════════════════════════════════════════════════════════"
echo "  DONE — output: out/TP-104 OVERLAY_C.dxf"
echo "═══════════════════════════════════════════════════════════════"
