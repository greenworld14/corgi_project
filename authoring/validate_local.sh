#!/usr/bin/env bash
# Local validation of the bundle on a Docker machine, AFTER run_freeze.sh has
# populated tests/hidden and cases/visible.
#
# Preferred path is the real harness if you have it:
#     cd bundle && harbor run -p . -a oracle -e docker -k 1   # expect ~1.0
#     cd bundle && harbor run -p . -a nop    -e docker -k 1   # expect the floor
#
# This script is a harness-independent sanity check using plain Docker. It
# reproduces the sealed layout: the candidate lives in /app, and tests/ is
# mounted OUTSIDE /app so it is unreachable from the candidate's view.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO/bundle"

IMG=pp-task:latest

echo "==> building task image"
docker build -t "$IMG" environment

echo "==> asserting no C preprocessor baked into the image"
if docker run --rm "$IMG" sh -c 'command -v cpp gcc cc clang tcc 2>/dev/null'; then
  echo "FAIL: a preprocessor is present in the task image" >&2
  exit 1
fi
echo "    ok (none found)"

run_grade () {
  # $1 = mode (oracle|nop)
  local mode="$1"
  local apply=""
  if [ "$mode" = "oracle" ]; then
    apply='bash /grading/solution/solve.sh &&'
  fi
  docker run --rm \
    -v "$REPO/bundle/tests":/grading/tests:ro \
    -v "$REPO/bundle/solution":/grading/solution:ro \
    "$IMG" bash -euo pipefail -c "
      $apply
      TASK_BUDGET_SECS=600 /app/timer.sh &
      bash /grading/tests/test.sh /grading
      echo '---REWARD---'
      cat /grading/reward.txt
    "
}

echo "==> NOP run (untouched stub) — expect <= 0.15"
nop_out="$(run_grade nop)"
echo "$nop_out" | sed -n '/REWARD/,$p'
nop="$(echo "$nop_out" | tail -1)"

echo "==> ORACLE run (reference) — expect ~1.0"
oracle_out="$(run_grade oracle)"
echo "$oracle_out" | sed -n '/REWARD/,$p'
oracle="$(echo "$oracle_out" | tail -1)"

echo
echo "==> leak checks"
if grep -rIl -e compute_reward -e heldout -e expected.json environment/ 2>/dev/null; then
  echo "LEAK: grader artefacts reachable from environment/ — fix before submitting" >&2
  exit 1
fi
find environment -type d -name hidden -o -type f -name 'compute_reward.py' | grep . && {
  echo "LEAK: sealed files under environment/" >&2; exit 1; } || true
echo "    ok (no grader/reference/answers under environment/)"

echo
echo "==> summary"
echo "    nop    reward = $nop   (must be <= 0.15)"
echo "    oracle reward = $oracle (must be ~1.0)"
awk -v n="$nop" -v o="$oracle" 'BEGIN{
  if (n+0 > 0.15) { print "    NOP ABOVE FLOOR — investigate"; bad=1 }
  if (o+0 < 0.95) { print "    ORACLE BELOW 0.95 — investigate"; bad=1 }
  if (!bad) print "    PASS"
}'
