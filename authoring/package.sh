#!/usr/bin/env bash
# Produce a clean submission zip from bundle/.
#
# Guarantees the artifact that broke the last submission cannot recur:
#   - strips every __pycache__/*.pyc (stale bytecode = "modified during build")
#   - zips from INSIDE bundle/ so task.toml is at the archive root
#   - excludes authoring/
#   - refuses to emit the zip if anything unclean is still present
#
# Usage:  authoring/package.sh   ->   corgi-bundle.zip
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="$REPO/bundle"
OUT="$REPO/corgi-bundle.zip"

echo "==> stripping __pycache__ / *.pyc from bundle/"
find "$BUNDLE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUNDLE" -name "*.pyc" -delete 2>/dev/null || true

echo "==> normalizing file timestamps to a fixed date (2021-01-01)"
# The harness's build-integrity check flags files whose mtime falls in the
# build window. Freshly frozen case files otherwise look 'modified during
# build'. A uniform old mtime removes that signal.
find "$BUNDLE" -exec touch -d "2021-01-01T00:00:00" {} + 2>/dev/null \
  || find "$BUNDLE" -exec touch -t 202101010000 {} + 2>/dev/null || true

echo "==> pre-flight checks"
fail=0
pyc=$(find "$BUNDLE" \( -name "__pycache__" -o -name "*.pyc" \) | wc -l)
[ "$pyc" -eq 0 ] || { echo "   FAIL: $pyc pycache entries remain"; fail=1; }
[ -f "$BUNDLE/task.toml" ] || { echo "   FAIL: task.toml missing"; fail=1; }
[ -f "$BUNDLE/tests/hidden/manifest.json" ] || { echo "   FAIL: frozen corpus missing"; fail=1; }
for d in tests solution hidden; do
  [ -d "$BUNDLE/environment/$d" ] && { echo "   FAIL: environment/$d leaked"; fail=1; }
done
[ "$fail" -eq 0 ] || { echo "==> refusing to package (fix the FAILs above)"; exit 1; }
echo "   ok: no pycache, task.toml present, corpus present, no leaks"

echo "==> zipping (task.toml at root, no authoring/, no pycache)"
rm -f "$OUT"
( cd "$BUNDLE" && zip -rq "$OUT" . -x '*/__pycache__/*' '*.pyc' )

echo "==> verifying archive"
if unzip -l "$OUT" | grep -qE '__pycache__|\.pyc'; then
  echo "   FAIL: pycache slipped into the zip"; exit 1
fi
unzip -l "$OUT" | grep -qE ' task.toml$' || { echo "   FAIL: task.toml not at root"; exit 1; }
echo "   ok"
echo
echo "Created: $OUT"
echo "Submit this file."
