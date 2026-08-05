"""Differential test: reference URL parser vs Node's URL on a batch of cases."""
import json
import os
import subprocess
import sys
import tempfile

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "bundle", "solution", "ref")
ORACLE = os.path.join(os.path.dirname(__file__), "url_oracle.js")
PY = sys.executable

CASES = [
    ("http://example.com/a/b/../c", None),
    ("HTTP://User:Pass@Example.COM:80/p?q#f", None),
    ("//host/path", "http://base/x"),
    ("../g", "http://a/b/c/d"),
    ("http://0x7f.1/", None),
    ("http://[::1]:8080/", None),
    ("file:///C:/x", None),
    ("foo:bar", None),
    ("a/b/c", "http://h/x/y"),
    ("http://h/%41%2f", None),
    ("https://host:443/path", None),
    ("http://h:80/", None),
    ("http://h/a//b///c", None),
    ("http://h/./a/../b", None),
    ("http://user@host/", None),
    ("http://:pass@host/", None),
    ("ftp://h/x", None),
    ("ws://h/x", None),
    ("mailto:a@b.com", None),
    ("data:text/plain,hi", None),
    ("http://h/ /?a b#c d", None),
    ("http://h/\u00e9", None),
    ("http://1.2.3.4/", None),
    ("http://0300.0250.0.1/", None),
    ("http://[2001:db8::1]/", None),
    ("http://[1:2:3:4:5:6:7:8]/", None),
    ("file://localhost/x", None),
    ("http://h/?", None),
    ("http://h/#", None),
    ("http://h", None),
    ("g", "http://a/b/c/d?q#f"),
    ("?y", "http://a/b/c/d?q#f"),
    ("#s", "http://a/b/c/d?q#f"),
    ("//g", "http://a/b/c/d"),
    ("http:g", "http://a/b/c/d"),
    ("", "http://a/b/c/d?q#f"),
    (".", "http://a/b/c/d"),
    ("..", "http://a/b/c/d"),
    ("http://h\\path", None),
    ("HTTPS://H/PATH", None),
]


def run_ref(case):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(case, f)
        path = f.name
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.abspath(REF_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        r = subprocess.run([PY, "-m", "urlp", path], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        return ("err", r.stderr.strip())
    try:
        return ("ok", json.loads(r.stdout))
    except Exception:
        return ("bad", r.stdout[:200])


def run_node(case):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(case, f)
        path = f.name
    try:
        r = subprocess.run(["node", ORACLE, path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        os.unlink(path)
    if r.returncode != 0:
        return ("err", None)
    try:
        return ("ok", json.loads(r.stdout))
    except Exception:
        return ("bad", None)


def main():
    agree = disagree = 0
    for inp, base in CASES:
        case = {"input": inp, "base": base}
        rs, rv = run_ref(case)
        ns, nv = run_node(case)
        if rs == "err" and ns == "err":
            agree += 1
            continue
        if rs == "ok" and ns == "ok" and rv == nv:
            agree += 1
            continue
        disagree += 1
        print("DISAGREE  input=%r base=%r" % (inp, base))
        print("   ref : %s %s" % (rs, json.dumps(rv.get("url") if isinstance(rv, dict) else rv, ensure_ascii=False) if rv else rv))
        print("   node: %s %s" % (ns, json.dumps(nv.get("url") if isinstance(nv, dict) else nv, ensure_ascii=False) if nv else nv))
    print("\n%d agree, %d disagree, %d total" % (agree, disagree, len(CASES)))
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main())
