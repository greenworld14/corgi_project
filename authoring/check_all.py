"""One-shot project checker.

Runs every gate that can be checked locally and prints a single PASS / FAIL /
WARN summary with an overall verdict. Pure stdlib; works on Windows (NDK python)
or Ubuntu (python3).

    python3 authoring/check_all.py

Exit code 0 only if there are no FAILs. WARNs (e.g. corpus not yet gcc-validated,
schema still guessed) do not fail the run but ARE listed and block submission.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "bundle")
HIDDEN = os.path.join(BUNDLE, "tests", "hidden")
ENVDIR = os.path.join(BUNDLE, "environment")
PY = sys.executable

# Blocked / provenance-risk vocabulary that must not appear in the shipped
# bundle instruction text.
BLOCKED = ["held-out", "heldout", "reward hack", "reward-hack", "the solver",
           "harbor", "difficulty probe", "oracle", "benchmark"]
BUNDLE_TEXT_FILES = ["instruction.md"]

results = []  # (level, name, detail)


def add(level, name, detail=""):
    results.append((level, name, detail))


def run(cmd):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def check_selftest():
    r = run([PY, "authoring/url_difftest.py"])
    last = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode == 0 and "0 disagree" in last:
        add("PASS", "reference vs Node self-test", last)
    else:
        add("FAIL", "reference vs Node self-test", last or r.stderr.strip()[-200:])


def check_verifier():
    if not os.path.isfile(os.path.join(HIDDEN, "manifest.json")):
        add("FAIL", "oracle/nop scoring", "no frozen corpus at tests/hidden")
        return
    r = run([PY, "authoring/test_verifier.py", "--hidden", HIDDEN])
    ref = stub = None
    for line in r.stdout.splitlines():
        if "reference reward" in line:
            ref = line.split("=")[1].strip().split()[0]
        if "stub reward" in line:
            stub = line.split("=")[1].strip().split()[0]
    try:
        okref = ref is not None and float(ref) >= 0.95
        okstub = stub is not None and float(stub) <= 0.15
    except (ValueError, TypeError):
        okref = okstub = False
    if okref and okstub:
        add("PASS", "oracle/nop scoring", "reference=%s  stub=%s" % (ref, stub))
    else:
        add("FAIL", "oracle/nop scoring",
            "reference=%s (need >=0.95)  stub=%s (need <=0.15)" % (ref, stub))


def check_structure():
    required = [
        "task.toml", "instruction.md", "job.yaml", "oracle.yaml",
        os.path.join("environment", "Dockerfile"),
        os.path.join("environment", "timer.sh"),
        os.path.join("environment", "check.py"),
        os.path.join("tests", "test.sh"),
        os.path.join("tests", "compute_reward.py"),
        os.path.join("solution", "solve.sh"),
    ]
    missing = [f for f in required if not os.path.isfile(os.path.join(BUNDLE, f))]
    if missing:
        add("FAIL", "required files present", "missing: " + ", ".join(missing))
    else:
        add("PASS", "required files present", "%d required files" % len(required))

    dpath = os.path.join(ENVDIR, "Dockerfile")
    bad = []
    with open(dpath, encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if s.startswith("#"):
                continue
            if s.startswith("ENV") and "BASH_ENV" in s:
                bad.append("ENV BASH_ENV directive")
            if "printf" in s and "timer" in s:
                bad.append("printf timer bootstrap")
    if bad:
        add("FAIL", "Dockerfile timer policy", "; ".join(bad))
    else:
        add("PASS", "Dockerfile timer policy", "no autostart (COPY + chmod only)")


def check_leaks():
    leaks = []
    for root, dirs, files in os.walk(ENVDIR):
        rp = root.replace("\\", "/")
        for fn in files:
            if fn.lower() == "compute_reward.py":
                leaks.append(os.path.relpath(os.path.join(root, fn), BUNDLE))
            if fn == "manifest.json" and "/cases/" not in rp + "/":
                leaks.append(os.path.relpath(os.path.join(root, fn), BUNDLE))
    for bad in ("tests", "solution", "hidden"):
        if os.path.isdir(os.path.join(ENVDIR, bad)):
            leaks.append("environment/%s/" % bad)
    if leaks:
        add("FAIL", "no grader/answers under environment/", "; ".join(leaks))
    else:
        add("PASS", "no grader/answers under environment/", "environment/ is clean")


def check_corpus():
    man = os.path.join(HIDDEN, "manifest.json")
    if not os.path.isfile(man):
        add("FAIL", "frozen corpus present", "tests/hidden/manifest.json missing")
        return
    with open(man, encoding="utf-8") as f:
        entries = json.load(f)
    n = len(entries)
    broken = 0
    cats = {}
    for e in entries:
        cdir = os.path.join(HIDDEN, e["id"])
        if not os.path.isfile(os.path.join(cdir, "expected.json")) or \
           not os.path.isfile(os.path.join(cdir, e["entry"])):
            broken += 1
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    if n == 0:
        add("FAIL", "frozen corpus intact", "0 cases")
    elif broken:
        add("FAIL", "frozen corpus intact", "%d cases missing files" % broken)
    else:
        thin = [c for c, k in cats.items() if k < 5]
        detail = "%d cases across %d categories" % (n, len(cats))
        add("WARN" if thin else "PASS", "frozen corpus intact",
            detail + ("; thin: " + ",".join(thin) if thin else ""))


def check_gcc_validated():
    rep = os.path.join(REPO, "authoring", "candidates_url", "freeze_report.json")
    if not os.path.isfile(rep):
        add("WARN", "corpus is cross-validated",
            "no freeze report — run freeze_url.py with Node, then re-check")
        return
    with open(rep, encoding="utf-8") as f:
        r = json.load(f)
    if r.get("node_validated"):
        dd = r.get("stats", {}).get("drop_disagree", "?")
        add("PASS", "corpus is cross-validated", "Node cross-check ran (drop_disagree=%s)" % dd)
    else:
        add("WARN", "corpus is cross-validated",
            "corpus is REFERENCE-ONLY (--no-node); re-run freeze_url.py with Node")


def check_blocked_terms():
    hits = []
    for rel in BUNDLE_TEXT_FILES:
        p = os.path.join(BUNDLE, rel)
        if not os.path.isfile(p):
            continue
        text = open(p, encoding="utf-8", errors="ignore").read().lower()
        for term in BLOCKED:
            if term in text:
                hits.append("%s: '%s'" % (rel, term.strip()))
    if hits:
        add("WARN", "no blocked vocabulary in instruction.md", "review: " + "; ".join(hits))
    else:
        add("PASS", "no blocked vocabulary in instruction.md", "clean scan")


def check_schema_guesses():
    n = 0
    for rel in ("task.toml", "job.yaml", "oracle.yaml"):
        p = os.path.join(BUNDLE, rel)
        if os.path.isfile(p):
            n += open(p, encoding="utf-8", errors="ignore").read().count("GUESS")
    if n == 0:
        add("PASS", "schema confirmed", "no GUESS markers left")
    else:
        add("WARN", "schema confirmed",
            "%d GUESS markers remain — confirm job.yaml/oracle.yaml/category" % n)


def main():
    check_selftest()
    check_verifier()
    check_structure()
    check_leaks()
    check_corpus()
    check_gcc_validated()
    check_blocked_terms()
    check_schema_guesses()

    width = max(len(n) for _, n, _ in results)
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}
    print()
    for level, name, detail in results:
        print("%s %-*s  %s" % (icon[level], width, name, detail))
    fails = sum(1 for l, _, _ in results if l == "FAIL")
    warns = sum(1 for l, _, _ in results if l == "WARN")
    print()
    if fails:
        print("VERDICT: %d FAIL, %d WARN -- NOT correct yet." % (fails, warns))
    elif warns:
        print("VERDICT: all gates PASS, %d WARN -- locally correct, "
              "NOT submittable until warnings are cleared." % warns)
    else:
        print("VERDICT: all gates PASS, 0 WARN -- ready to package and submit.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
