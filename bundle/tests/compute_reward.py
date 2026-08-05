#!/usr/bin/env python3
"""Sealed verifier for the URL-parser task.

Runs the candidate at /app against the frozen conformance set under
tests/hidden/, scores a weighted exact-match fraction in [0, 1], and writes
reward.json + reward.txt.

Invariants honoured:
  * Hard gate -> 0: if the candidate cannot run at all, every case fails and the
    reward is 0. Cheat detection (an available external JS runtime) forces 0.
  * Fixed denominator: crashes, timeouts, malformed output and skipped cases all
    count as failures against the full weighted total.
  * Sealed: only source files are exposed to the candidate; expected outputs and
    this script live under tests/ and are never copied into the candidate's view.
  * Deterministic and bounded: per-case timeout, no randomness.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# Path overrides exist only so the corpus can live elsewhere during authoring;
# they carry no answer data and do not weaken the cheat gate or env scrub.
HIDDEN = os.environ.get("PP_HIDDEN_DIR", os.path.join(HERE, "hidden"))
APP = os.environ.get("PP_APP_DIR", "/app")
PER_CASE_TIMEOUT = 15  # seconds

# A WHATWG-conformant URL parser ships with JS runtimes; their presence in the
# image would let a candidate shell out instead of implementing the parser.
_FORBIDDEN_BINS = ["node", "nodejs", "deno", "bun"]
_FORBIDDEN_PATHS = ["/usr/bin", "/bin", "/usr/local/bin", "/opt/bin"]


def cheat_environment():
    """Return a reason string if a JS runtime is reachable, else None."""
    for d in _FORBIDDEN_PATHS:
        for b in _FORBIDDEN_BINS:
            p = os.path.join(d, b)
            if os.path.exists(p):
                return "external JS runtime present: %s" % p
    return None


def child_env():
    return {
        "PATH": "",                       # candidate cannot spawn a JS runtime
        "PYTHONPATH": APP,                # its own `urlp` package, nothing else
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "HOME": "/tmp",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


def run_case(py, case_dir, entry):
    """Run the candidate on one case in an isolated scratch copy."""
    with tempfile.TemporaryDirectory() as scratch:
        for fname in os.listdir(case_dir):
            if fname == "expected.json":
                continue  # never expose the answer
            shutil.copy(os.path.join(case_dir, fname), os.path.join(scratch, fname))
        try:
            r = subprocess.run(
                [py, "-m", "urlp", entry],
                cwd=scratch,
                env=child_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PER_CASE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return ("timeout", None)
        except Exception:
            return ("crash", None)
    if r.returncode != 0:
        return ("err", None)
    try:
        return ("ok", json.loads(r.stdout))
    except Exception:
        return ("badjson", None)


def case_passes(expected, status, output):
    if expected.get("error"):
        # A URL that fails to parse must be rejected with a non-zero exit.
        return status == "err"
    if status != "ok":
        return False
    if not isinstance(output, dict) or "url" not in output:
        return False
    return output["url"] == expected["url"]


def output_dirs():
    """Every directory the harness might read the reward from.

    The harness looks in the verifier's working directory; depending on how it
    invokes the entry point that is either the current directory or a path
    passed as argv[1]. Writing to both (deduplicated) is harmless and removes
    any ambiguity about where reward.json / reward.txt must land.
    """
    candidates = [HERE, os.getcwd()]

    # Every argument might be, or contain, the output directory -- the harness
    # may pass it at any position, possibly as --flag=value.
    for a in sys.argv[1:]:
        val = a
        if a.startswith("-") and "=" in a:
            val = a.split("=", 1)[1]
        candidates.append(val)
        candidates.append(os.path.dirname(val))

    # The reward location is almost certainly in SOME environment variable; we
    # just don't know its name. Scan every value for a verifier/output/reward
    # path and try both it and its parent. This is name-agnostic discovery.
    for v in os.environ.values():
        if not v:
            continue
        low = v.lower()
        if "/verifier" in v or "/work/jobs" in v or "reward" in low or "/output" in low:
            candidates.append(v)
            candidates.append(os.path.dirname(v))

    # Direct discovery of the reported path shape.
    for pat in ("/work/jobs/*/*/verifier", "/work/*/*/verifier",
                "/work/jobs/*/verifier", "/work/*/verifier",
                "/work/**/verifier", "/work/**/*verifier*"):
        try:
            candidates.extend(glob.glob(pat, recursive=True))
        except Exception:
            pass

    dirs = []
    for d in candidates:
        if not d:
            continue
        try:
            ad = os.path.abspath(d)
        except Exception:
            continue
        if os.path.isdir(ad) and os.access(ad, os.W_OK) and ad not in dirs:
            dirs.append(ad)
    if not dirs:
        dirs = [os.getcwd()]
    return dirs


def write_outputs(out_dir, payload):
    for d in output_dirs():
        try:
            with open(os.path.join(d, "reward.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            with open(os.path.join(d, "reward.txt"), "w", encoding="utf-8") as f:
                f.write("%.6f\n" % payload["reward"])
        except OSError:
            pass


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    py = sys.executable

    reason = cheat_environment()
    if reason is not None:
        payload = {"reward": 0.0, "gate": "cheat", "detail": reason,
                   "passed_weight": 0.0, "total_weight": 0.0}
        write_outputs(out_dir, payload)
        print("REWARD 0.0 (cheat gate: %s)" % reason)
        return 0

    try:
        with open(os.path.join(HIDDEN, "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        payload = {"reward": 0.0, "gate": "no_manifest", "detail": str(e),
                   "passed_weight": 0.0, "total_weight": 0.0}
        write_outputs(out_dir, payload)
        print("REWARD 0.0 (no manifest)")
        return 0

    total_w = 0.0
    passed_w = 0.0
    per_cat = {}
    fail_examples = []
    status_counts = {}

    for c in manifest:
        cid = c["id"]
        w = float(c["weight"])
        cat = c["category"]
        total_w += w
        stat = per_cat.setdefault(cat, {"pass": 0.0, "total": 0.0, "n": 0, "np": 0})
        stat["total"] += w
        stat["n"] += 1

        case_dir = os.path.join(HIDDEN, cid)
        try:
            with open(os.path.join(case_dir, "expected.json"), encoding="utf-8") as f:
                expected = json.load(f)
        except Exception:
            continue  # missing expected => counts as failure (denominator fixed)

        status, output = run_case(py, case_dir, c["entry"])
        status_counts[status] = status_counts.get(status, 0) + 1
        if case_passes(expected, status, output):
            passed_w += w
            stat["pass"] += w
            stat["np"] += 1
        elif len(fail_examples) < 25:
            fail_examples.append({"id": cid, "status": status})

    reward = (passed_w / total_w) if total_w > 0 else 0.0
    categories = {
        cat: {
            "fraction": (s["pass"] / s["total"]) if s["total"] else 0.0,
            "passed": s["np"],
            "total": s["n"],
        }
        for cat, s in sorted(per_cat.items())
    }
    payload = {
        "reward": round(reward, 6),
        "passed_weight": round(passed_w, 4),
        "total_weight": round(total_w, 4),
        "cases_total": len(manifest),
        "categories": categories,
        "status_counts": status_counts,
        "diagnostics": {
            "app_dir": APP,
            "app_urlp_exists": os.path.isdir(os.path.join(APP, "urlp")),
            "hidden_dir": HIDDEN,
            "python": py,
        },
        "sample_failures": fail_examples,
    }
    write_outputs(out_dir, payload)
    print("REWARD %.6f  (%d/%d cases, weighted %.2f/%.2f)"
          % (reward, sum(s["np"] for s in per_cat.values()),
             len(manifest), passed_w, total_w))
    for cat, info in categories.items():
        print("  %-14s %3d/%-3d  %.3f" % (cat, info["passed"], info["total"],
                                          info["fraction"]))
    return 0


if __name__ == "__main__":
    # A verifier must emit a reward on every path. If anything unexpected throws,
    # still write a 0.0 reward with the traceback so the run is graded (and
    # diagnosable) instead of failing with "no reward file".
    try:
        rc = main()
    except Exception:
        import traceback
        payload = {"reward": 0.0, "gate": "verifier_crash",
                   "detail": traceback.format_exc()[-1500:],
                   "passed_weight": 0.0, "total_weight": 0.0}
        try:
            write_outputs(os.getcwd(), payload)
        except Exception:
            pass
        print("REWARD 0.0 (verifier crashed)", file=sys.stderr)
        rc = 0
    sys.exit(rc)
