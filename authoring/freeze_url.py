"""Freeze the URL-parser corpus: reference (in-process) vs Node oracle (batched).

The reference is imported and run in-process (fast); Node runs once over all
cases via a JSONL batch oracle. Cases where they agree are kept with the frozen
expected output; disagreements and mixed error/ok are dropped. A disjoint
visible sample is split out. Writes normalized (LF + trailing newline) files.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

VISIBLE_PER_CATEGORY = 3
HERE = os.path.dirname(os.path.abspath(__file__))
BATCH_ORACLE = os.path.join(HERE, "url_oracle_batch.js")


def load_reference(ref_dir):
    sys.path.insert(0, os.path.abspath(ref_dir))
    from urlp.machine import parse
    from urlp.parser import URLError
    from urlp.__main__ import components
    return parse, URLError, components


def ref_eval(parse, URLError, components, case):
    inp = case.get("input", "")
    base = case.get("base")
    try:
        base_url = parse(base) if base is not None else None
        if base is not None and base_url.scheme == "":
            return {"error": True}
        url = parse(inp, base_url)
        if url.scheme == "":
            return {"error": True}
    except URLError:
        return {"error": True}
    except Exception:
        return {"error": True}
    return {"url": components(url)}


def node_eval_all(node, cases):
    jsonl = "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n"
    r = subprocess.run([node, BATCH_ORACLE], input=jsonl, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    results = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            d = {"ok": False}
        results.append({"url": d["url"]} if d.get("ok") else {"error": True})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--ref-dir", required=True)
    ap.add_argument("--out-hidden", required=True)
    ap.add_argument("--out-visible", required=True)
    ap.add_argument("--node", default="node")
    ap.add_argument("--no-node", action="store_true")
    args = ap.parse_args()

    parse, URLError, components = load_reference(args.ref_dir)
    with open(os.path.join(args.candidates, "candidates.json"), encoding="utf-8") as f:
        candidates = json.load(f)

    cases = []
    for c in candidates:
        with open(os.path.join(args.candidates, c["id"], c["entry"]), encoding="utf-8") as f:
            cases.append(json.load(f))

    ref_out = [ref_eval(parse, URLError, components, cs) for cs in cases]
    if args.no_node:
        node_out = ref_out
    else:
        node_out = node_eval_all(args.node, cases)
        if len(node_out) != len(cases):
            print("WARN: node returned %d results for %d cases" % (len(node_out), len(cases)))

    kept = []
    stats = {"kept": 0, "drop_disagree": 0, "kept_error": 0, "drop_mixed": 0}
    for i, c in enumerate(candidates):
        rv = ref_out[i]
        nv = node_out[i] if i < len(node_out) else {"error": True}
        r_err = "error" in rv
        n_err = "error" in nv
        if r_err and n_err:
            kept.append((c, {"error": True})); stats["kept"] += 1; stats["kept_error"] += 1
        elif r_err != n_err:
            stats["drop_mixed"] += 1
        elif rv == nv:
            kept.append((c, rv)); stats["kept"] += 1
        else:
            stats["drop_disagree"] += 1

    visible_ids = _pick_visible(kept)
    write_corpus(args.out_hidden, [(c, e) for c, e in kept if c["id"] not in visible_ids], args.candidates)
    write_corpus(args.out_visible, [(c, e) for c, e in kept if c["id"] in visible_ids], args.candidates)

    by_cat = {}
    for c, _ in kept:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    report = {"node_validated": not args.no_node, "stats": stats,
              "by_category": by_cat, "hidden": stats["kept"] - len(visible_ids),
              "visible": len(visible_ids)}
    with open(os.path.join(args.candidates, "freeze_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("freeze complete:")
    for k, v in stats.items():
        print("  %-16s %d" % (k, v))
    print("  hidden           %d" % (stats["kept"] - len(visible_ids)))
    print("  visible          %d" % len(visible_ids))
    print("kept by category:")
    for cat in sorted(by_cat):
        print("  %-12s %d" % (cat, by_cat[cat]))


def _pick_visible(kept):
    per = {}
    chosen = set()
    for c, e in kept:
        if e == {"error": True}:
            continue
        cat = c["category"]
        if per.get(cat, 0) < VISIBLE_PER_CATEGORY:
            chosen.add(c["id"]); per[cat] = per.get(cat, 0) + 1
    return chosen


def write_corpus(out_dir, items, cand_dir):
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for c, expected in items:
        cid = c["id"]
        src = os.path.join(cand_dir, cid)
        dst = os.path.join(out_dir, cid)
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            data = open(os.path.join(src, fn), "rb").read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            if data and not data.endswith(b"\n"):
                data += b"\n"
            open(os.path.join(dst, fn), "wb").write(data)
        payload = (json.dumps(expected, ensure_ascii=False) + "\n").encode("utf-8")
        open(os.path.join(dst, "expected.json"), "wb").write(payload)
        manifest.append({"id": cid, "category": c["category"],
                         "weight": c["weight"], "entry": c["entry"]})
    payload = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    open(os.path.join(out_dir, "manifest.json"), "wb").write(payload)


if __name__ == "__main__":
    main()
