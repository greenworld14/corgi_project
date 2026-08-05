#!/usr/bin/env bash
# Sealed grader entry point.
#
# Invariant that dominates everything else here: a reward file MUST exist when we
# exit, or the run fails as an infra error ("no reward file") instead of being
# scored. So the FIRST thing we do -- before any command that could fail, before
# `set -u`, before locating anything -- is drop a floor reward into every
# plausible output directory. compute_reward.py then overwrites it with the real
# score. For the untouched state the floor (0.0) is already the correct answer,
# so even a total failure downstream still grades sanely.

emit_floor() {
  for d in "$@"; do
    [ -n "$d" ] || continue
    [ -d "$d" ] || continue
    { printf '%s\n' '{"reward": 0.0, "gate": "pending"}' > "$d/reward.json"; } 2>/dev/null || true
    { printf '0.0\n' > "$d/reward.txt"; } 2>/dev/null || true
  done
}

ARG_DIR="${1:-}"
CWD="$(pwd)"

# Locate this script's directory robustly under either bash or a POSIX shell.
# The harness's output path is named ".../verifier/" -- i.e. where these scripts
# are placed -- so the reward almost certainly belongs next to this script.
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
if [ -z "$HERE" ] || [ ! -f "$HERE/compute_reward.py" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
fi
ARG_PARENT=""
[ -n "$ARG_DIR" ] && ARG_PARENT="$(dirname "$ARG_DIR" 2>/dev/null || true)"

# Discover the output directory rather than guessing how it is passed in:
#  (1) the reported path shape /work/jobs/<job>/<task>/verifier/
#  (2) any argument that is a directory (any position, incl. --flag=value)
#  (3) any environment VALUE that looks like a verifier/output/reward path
HARNESS_DIRS=""
add_dir() { [ -n "$1" ] && [ -d "$1" ] && HARNESS_DIRS="$HARNESS_DIRS $1"; }

for d in /work/jobs/*/*/verifier /work/*/*/verifier /work/jobs/*/verifier /work/*/verifier; do
  add_dir "$d"
done
for a in "$@"; do
  case "$a" in --*=*) a="${a#*=}";; esac
  add_dir "$a"
  add_dir "$(dirname "$a" 2>/dev/null)"
done
while IFS='=' read -r _k _v; do
  case "$_v" in
    */verifier|*/verifier/|*/work/jobs/*|*/output|*/output/) add_dir "$_v"; add_dir "$(dirname "$_v" 2>/dev/null)";;
  esac
done <<EOF
$(env 2>/dev/null)
EOF

# Floor reward into EVERY plausible location before anything can fail.
# shellcheck disable=SC2086
emit_floor "$HERE" "$CWD" "$ARG_DIR" "$ARG_PARENT" "${REWARD_DIR:-}" "${OUTPUT_DIR:-}" $HARNESS_DIRS

# --- runtime diagnostics ---------------------------------------------------
# Printed to stderr (captured in the verifier log) so the exact working
# directory, arguments, environment and filesystem layout are visible if a
# reward file still can't be placed. Harmless to grading (only reward.* is read).
{
  echo "=== PP VERIFIER DEBUG ==="
  echo "pwd=$CWD"
  echo "arg0=$0"
  echo "HERE=$HERE"
  echo "args=[$*]"
  echo "uid=$(id 2>/dev/null || echo '?')"
  echo "--- env (sorted) ---"; env 2>/dev/null | sort
  echo "--- ls -la pwd ---"; ls -la . 2>/dev/null
  echo "--- ls -la HERE ---"; ls -la "$HERE" 2>/dev/null
  echo "--- /work tree (depth 5) ---"; find /work -maxdepth 5 2>/dev/null | head -60
  echo "--- writable verifier dirs ---"
  for d in /work/jobs/*/*/verifier /work/*/*/verifier; do
    [ -d "$d" ] && printf '%s writable=%s\n' "$d" "$([ -w "$d" ] && echo yes || echo no)"
  done
  echo "=== END PP VERIFIER DEBUG ==="
} >&2

# Where the real score should be written (argv 1, else the current directory).
OUT_DIR="${ARG_DIR:-$CWD}"

# --- environment hardening -------------------------------------------------
# Strip anything that could let the candidate preload code or reach a tool it
# should not, and stop background file watchers that could race the scratch dir.
unset PYTHONPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONSTARTUP PYTHONHOME BASH_ENV 2>/dev/null || true
export PYTHONDONTWRITEBYTECODE=1
pkill -f inotifywait >/dev/null 2>&1 || true
pkill -f watchman    >/dev/null 2>&1 || true

# The grader's own interpreter (not one the candidate can shadow via PATH).
PYTHON="$(command -v python3 2>/dev/null || true)"
[ -n "$PYTHON" ] || PYTHON="$(command -v python 2>/dev/null || true)"

# compute_reward.py enforces the remaining invariants (cheat gate, fixed
# denominator, per-case timeout) and writes reward.json + reward.txt to every
# plausible location itself. Any failure leaves the floor reward in place.
if [ -n "$PYTHON" ] && [ -n "$HERE" ] && [ -f "$HERE/compute_reward.py" ]; then
  "$PYTHON" "$HERE/compute_reward.py" "$OUT_DIR" 2>&1 || true
fi

exit 0
