#!/usr/bin/env bash
# Freeze the conformance corpus into the bundle. Run this on a machine with
# Docker. It builds a throwaway gcc+python image, generates candidates, runs the
# reference + gcc cross-check, and writes the gcc-validated frozen set into:
#
#   bundle/tests/hidden/            (sealed graded set)
#   bundle/environment/cases/visible/   (visible sample shipped in the image)
#
# Usage:  authoring/run_freeze.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "==> building freeze image (gcc + python3)"
docker build -f authoring/freeze/Dockerfile.freeze -t pp-freeze:latest authoring/freeze

echo "==> generating candidates + cross-checking against gcc"
docker run --rm -v "$REPO":/work -w /work pp-freeze:latest bash -euo pipefail -c '
  gcc --version | head -1
  rm -rf authoring/candidates
  python3 authoring/gen_cases.py authoring/candidates
  python3 authoring/freeze.py \
    --candidates authoring/candidates \
    --ref-dir bundle/solution/ref \
    --out-hidden bundle/tests/hidden \
    --out-visible bundle/environment/cases/visible \
    --gcc gcc --python python3
'

echo
echo "==> hidden cases : $(ls -d bundle/tests/hidden/*/ 2>/dev/null | wc -l)"
echo "==> visible cases: $(ls -d bundle/environment/cases/visible/*/ 2>/dev/null | wc -l)"
echo "Freeze complete. Review the per-category yield above before validating."
