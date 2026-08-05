#!/usr/bin/env bash
# Reference solution: install the complete URL parser into /app/urlp, replacing
# the shipped stub. Scores ~1.0 against the frozen conformance set.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

rm -rf /app/urlp
cp -r "$HERE/ref/urlp" /app/urlp

# Sanity: the module must at least import and run on the visible sample.
python3 - <<'PY'
import glob, os, subprocess, sys
cases = sorted(glob.glob("/app/cases/visible/*/input.json"))
if not cases:
    sys.exit(0)
r = subprocess.run(["python3", "-m", "urlp", cases[0]], cwd="/app",
                   capture_output=True, text=True)
if r.returncode not in (0, 1):
    sys.stderr.write("reference failed to run: %s\n" % r.stderr)
    sys.exit(1)
print("reference installed; sample ran with exit", r.returncode)
PY
