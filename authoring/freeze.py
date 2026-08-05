"""Freeze the conformance corpus.

For every candidate case, run the reference preprocessor and (unless --no-gcc)
`gcc -E` with pinned flags, tokenise both to the canonical stream, and keep the
case only when they agree. Surviving cases are written with their frozen
expected output:

  <out-hidden>/manifest.json
  <out-hidden>/<id>/<source files>
  <out-hidden>/<id>/expected.json      # {"tokens":[...]}  or  {"error": true}

A small disjoint sample is copied to <out-visible> for the agent's local
self-check; those cases are removed from the hidden set so "optimise for the
hidden set" is literally true.

This MUST run on a machine with gcc for a real freeze. --no-gcc produces a
reference-only corpus for local dry-runs and is NOT valid for submission.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

VISIBLE_PER_CATEGORY = 3

GCC_FLAGS = [
    "-undef", "-std=gnu11", "-E", "-P", "-nostdinc",
    "-D__STDC__=1", "-D__STDC_VERSION__=201112L", "-D__STDC_HOSTED__=1",
]


def load_ref(ref_dir):
    sys.path.insert(0, os.path.abspath(ref_dir))
    import pp.tokenizer as tkmod
    import pp.__main__ as mainmod
    return tkmod, mainmod


def run_reference(py, ref_dir, cdir, entry):
    env = dict(os.environ)
    # Make the `pp` package importable while cwd is the case dir (so __FILE__
    # stays the bare entry name, matching the gcc invocation).
    env["PYTHONPATH"] = os.path.abspath(ref_dir) + os.pathsep + env.get("PYTHONPATH", "")
    r = subprocess.run(
        [py, "-m", "pp", entry, "-I."],
        cwd=cdir, capture_output=True, text=True, env=env,
    )
    if r.returncode == 0:
        try:
            return ("ok", json.loads(r.stdout))
        except Exception:
            return ("bad", None)
    return ("err", None)


def run_gcc(gcc, cdir, entry):
    r = subprocess.run(
        [gcc] + GCC_FLAGS + ["-I.", entry],
        cwd=cdir, capture_output=True, text=True,
    )
    if r.returncode == 0:
        return ("ok", r.stdout)
    return ("err", None)


def tokenize_text(tkmod, mainmod, text):
    toks = tkmod.strip_newlines(tkmod.tokenize(text, "gcc"))
    return mainmod.render(toks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--ref-dir", required=True)
    ap.add_argument("--out-hidden", required=True)
    ap.add_argument("--out-visible", required=True)
    ap.add_argument("--gcc", default="gcc")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--no-gcc", action="store_true")
    args = ap.parse_args()

    tkmod, mainmod = load_ref(args.ref_dir)

    with open(os.path.join(args.candidates, "candidates.json"), encoding="utf-8") as f:
        candidates = json.load(f)

    kept = []
    stats = {"kept": 0, "drop_disagree": 0, "drop_refbad": 0,
             "kept_error": 0, "drop_mixed": 0}

    for c in candidates:
        cid = c["id"]
        cdir = os.path.join(args.candidates, cid)
        entry = c["entry"]

        ref_status, ref_out = run_reference(args.python, args.ref_dir, cdir, entry)
        if ref_status == "bad":
            stats["drop_refbad"] += 1
            continue

        if args.no_gcc:
            expected = {"error": True} if ref_status == "err" else ref_out
            kept.append((c, expected))
            stats["kept"] += 1
            continue

        gcc_status, gcc_text = run_gcc(args.gcc, cdir, entry)

        if ref_status == "err" and gcc_status == "err":
            kept.append((c, {"error": True}))
            stats["kept"] += 1
            stats["kept_error"] += 1
            continue
        if ref_status == "err" or gcc_status == "err":
            stats["drop_mixed"] += 1
            continue

        gcc_tokens = tokenize_text(tkmod, mainmod, gcc_text)
        if gcc_tokens == ref_out:
            kept.append((c, ref_out))
            stats["kept"] += 1
        else:
            stats["drop_disagree"] += 1

    # Split off a disjoint visible sample.
    visible_ids = _pick_visible(kept)
    write_corpus(args.out_hidden, [(c, e) for (c, e) in kept if c["id"] not in visible_ids],
                 args.candidates)
    write_corpus(args.out_visible, [(c, e) for (c, e) in kept if c["id"] in visible_ids],
                 args.candidates)

    by_cat = {}
    for c, _ in kept:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1

    # Provenance report so the project checker can tell a real cross-checked
    # corpus from a reference-only dry-run. Written into the candidates dir,
    # which is never shipped in the bundle.
    report = {
        "gcc_validated": not args.no_gcc,
        "compiler": None if args.no_gcc else args.gcc,
        "stats": stats,
        "by_category": by_cat,
        "hidden": stats["kept"] - len(visible_ids),
        "visible": len(visible_ids),
    }
    try:
        with open(os.path.join(args.candidates, "freeze_report.json"), "w",
                  encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except OSError:
        pass

    print("freeze complete:")
    for k, v in stats.items():
        print("  %-16s %d" % (k, v))
    print("  hidden           %d" % (stats["kept"] - len(visible_ids)))
    print("  visible          %d" % len(visible_ids))
    print("kept by category:")
    for cat in sorted(by_cat):
        print("  %-14s %d" % (cat, by_cat[cat]))


def _pick_visible(kept):
    per = {}
    chosen = set()
    for c, e in kept:
        # Prefer non-error cases as worked examples.
        if e == {"error": True}:
            continue
        cat = c["category"]
        if per.get(cat, 0) < VISIBLE_PER_CATEGORY:
            chosen.add(c["id"])
            per[cat] = per.get(cat, 0) + 1
    return chosen


def write_corpus(out_dir, items, cand_dir):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for c, expected in items:
        cid = c["id"]
        src_dir = os.path.join(cand_dir, cid)
        dst_dir = os.path.join(out_dir, cid)
        os.makedirs(dst_dir, exist_ok=True)
        for fname in os.listdir(src_dir):
            src = os.path.join(src_dir, fname)
            data = open(src, "rb").read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            if data and not data.endswith(b"\n"):
                data += b"\n"
            open(os.path.join(dst_dir, fname), "wb").write(data)
        payload = (json.dumps(expected, ensure_ascii=False) + "\n").encode("utf-8")
        open(os.path.join(dst_dir, "expected.json"), "wb").write(payload)
        manifest.append({
            "id": cid,
            "category": c["category"],
            "weight": c["weight"],
            "entry": c["entry"],
        })
    payload = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    open(os.path.join(out_dir, "manifest.json"), "wb").write(payload)


if __name__ == "__main__":
    main()
