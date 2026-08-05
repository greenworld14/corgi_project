#!/usr/bin/env python3
"""Local self-check: estimate your score on the VISIBLE sample.

    python3 /app/check.py            # score every visible case
    python3 /app/check.py -v         # also print each failing case

This runs your `pp` exactly as the grader does and compares against the visible
expected outputs in /app/cases/visible. It is only a sample: the hidden set is
much larger and covers more of the behavioural surface, so a high score here is
necessary but not sufficient. This script never has access to the hidden set.
"""
import json
import os
import subprocess
import sys
import tempfile
import shutil

APP = os.path.dirname(os.path.abspath(__file__))
VISIBLE = os.path.join(APP, "cases", "visible")
TIMEOUT = 15


def run_case(case_dir, entry):
    with tempfile.TemporaryDirectory() as scratch:
        for f in os.listdir(case_dir):
            if f == "expected.json":
                continue
            shutil.copy(os.path.join(case_dir, f), os.path.join(scratch, f))
        try:
            r = subprocess.run([sys.executable, "-m", "urlp", entry],
                               cwd=scratch, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return ("timeout", None)
    if r.returncode != 0:
        return ("err", r.stderr.strip())
    try:
        return ("ok", json.loads(r.stdout))
    except Exception:
        return ("badjson", r.stdout[:200])


def passes(expected, status, output):
    if expected.get("error"):
        return status == "err"
    return status == "ok" and isinstance(output, dict) \
        and output.get("url") == expected["url"]


def main():
    verbose = "-v" in sys.argv[1:]
    mpath = os.path.join(VISIBLE, "manifest.json")
    if not os.path.isfile(mpath):
        print("no visible manifest at %s" % mpath)
        return 1
    with open(mpath, encoding="utf-8") as f:
        manifest = json.load(f)

    total_w = passed_w = 0.0
    per_cat = {}
    for c in manifest:
        w = float(c.get("weight", 1.0))
        total_w += w
        s = per_cat.setdefault(c["category"], [0.0, 0.0])
        s[1] += w
        cdir = os.path.join(VISIBLE, c["id"])
        with open(os.path.join(cdir, "expected.json"), encoding="utf-8") as f:
            expected = json.load(f)
        status, output = run_case(cdir, c["entry"])
        if passes(expected, status, output):
            passed_w += w
            s[0] += w
        elif verbose:
            print("FAIL %-20s status=%s" % (c["id"], status))
            if status in ("err", "badjson"):
                print("     %s" % output)

    est = passed_w / total_w if total_w else 0.0
    print("\nvisible score estimate: %.3f  (%.1f / %.1f weighted)"
          % (est, passed_w, total_w))
    for cat in sorted(per_cat):
        p, t = per_cat[cat]
        print("  %-14s %.3f" % (cat, p / t if t else 0.0))
    print("\nreminder: the hidden set is larger and broader than this sample.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
