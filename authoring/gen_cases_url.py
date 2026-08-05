"""Deterministic candidate-case generator for the URL-parser task.

Each case is a directory containing input.json: {"input": "<string>",
"base": "<string>"|null}. Generation is seeded so the corpus reproduces exactly
on the freeze machine. freeze_url.py runs the reference + Node oracle and keeps
only cases where they agree. Non-ASCII domains are avoided (the reference does
not implement IDNA/punycode); non-ASCII in path/query/fragment is fine because
it is percent-encoded identically.
"""
import json
import os
import random
import sys

SEED = 0x1CE

CATEGORIES = {
    "scheme": 1.0,
    "authority": 1.5,
    "host_domain": 1.0,
    "host_ipv4": 1.5,
    "host_ipv6": 1.5,
    "port": 1.0,
    "path": 1.5,
    "opaque": 1.0,
    "queryfrag": 1.0,
    "relative": 2.0,
    "encoding": 1.5,
    "errors": 1.0,
}

SPECIAL_SCHEMES = ["http", "https", "ws", "wss", "ftp"]
HOSTS = ["h", "host", "example.com", "a.b.c", "sub.domain.org", "localhost"]
BASES = [
    "http://a/b/c/d?q#f", "http://a/b/c/d", "https://h:8/x/y/z",
    "ftp://u:p@host/dir/file", "file:///C:/dir/file", "http://h/",
    "foo:opaque", "http://user@h/p",
]


def rhost(r):
    return r.choice(HOSTS)


def gen_scheme(r):
    s = r.choice(SPECIAL_SCHEMES + ["file", "foo", "bar+baz", "a-b.c"])
    if s == "file":
        inp = "file://" + r.choice(["", "localhost"]) + "/" + r.choice(["x", "C:/y", "a/b"])
    elif s in SPECIAL_SCHEMES:
        inp = "%s://%s/%s" % (s, rhost(r), r.choice(["", "p", "a/b"]))
    else:
        inp = "%s:%s" % (s, r.choice(["opaque", "//h/p", "x?y#z"]))
    if r.random() < 0.3:
        inp = "".join(ch.upper() if r.random() < 0.5 else ch for ch in inp)
    return inp, None


def gen_authority(r):
    user = r.choice(["", "user", "u:p", ":pass", "a%40b", "user:"])
    host = rhost(r)
    port = r.choice(["", "", ":8080", ":80", ":0"])
    scheme = r.choice(SPECIAL_SCHEMES)
    at = "@" if user else ""
    return "%s://%s%s%s%s/p" % (scheme, user, at, host, port), None


def gen_host_domain(r):
    labels = [r.choice(["a", "host", "example", "sub", "test", "www", "x1",
                        "my-site", "node", "srv", "b2b"]) for _ in range(r.randint(1, 4))]
    dom = ".".join(labels)
    if r.random() < 0.35:
        dom = "".join(ch.upper() if r.random() < 0.5 else ch for ch in dom)
    if r.random() < 0.2:
        dom += "."
    return "http://%s/" % dom, None


def gen_host_ipv4(r):
    def part(last=False):
        style = r.randint(0, 4)
        v = r.randint(0, 255)
        if style == 0:
            return str(v)
        if style == 1:
            return "0x%x" % v
        if style == 2:
            return "0%o" % v if v else "00"
        if style == 3 and last:
            return str(r.randint(256, 4294967295))
        return str(r.randint(0, 300))
    n = r.randint(1, 4)
    host = ".".join(part(last=(i == n - 1)) for i in range(n))
    if r.random() < 0.15:
        host += "."
    return "http://%s/" % host, None


def gen_host_ipv6(r):
    def hx():
        return "%x" % r.randint(0, 0xFFFF)
    style = r.randint(0, 5)
    if style == 0:
        addr = ":".join(hx() for _ in range(8))
    elif style == 1:
        a = r.randint(1, 6)
        b = r.randint(0, 7 - a)
        addr = ":".join(hx() for _ in range(a)) + "::" + ":".join(hx() for _ in range(b))
    elif style == 2:
        addr = "::" + hx()
    elif style == 3:
        addr = "::ffff:%d.%d.%d.%d" % tuple(r.randint(0, 255) for _ in range(4))
    elif style == 4:
        addr = "::"
    else:
        addr = ":".join(hx() for _ in range(r.randint(2, 9)))  # sometimes invalid
    port = r.choice(["", "", ":8080", ":443", ":0"])
    return "http://[%s]%s/p" % (addr, port), None


def gen_port(r):
    scheme = r.choice(SPECIAL_SCHEMES)
    default = {"http": 80, "https": 443, "ws": 80, "wss": 443, "ftp": 21}[scheme]
    port = r.choice([str(default), "8080", "0", "1", "65535", ""])
    colon = ":" + port if port != "" else ""
    return "%s://h%s/path" % (scheme, colon), None


def gen_path(r):
    scheme = r.choice(SPECIAL_SCHEMES + ["foo"])
    segs = r.choice([
        "/a/b/../c", "/./a/./b", "/a//b///c", "/a/b/..", "/../../x",
        "/a/b/.", "/", "//", "/a/b/c", "/x/../../../y", "\\a\\b",
        "/a/b\\c", "/end/.", "/end/..",
    ])
    if scheme == "foo":
        return "foo://h%s" % segs, None
    return "%s://h%s" % (scheme, segs), None


def gen_opaque(r):
    scheme = r.choice(["mailto", "data", "javascript", "urn", "tel", "foo",
                       "bar", "custom", "x-scheme", "git+ssh"])
    body = r.choice(["a@b.com", "text/plain,hi", "void(0)", "isbn:123",
                     "+1-555", "opaque", "x?y#z", "/a/b/../c", "%41%42",
                     "//h/p", "", "a b c", "éé"])
    return "%s:%s" % (scheme, body), None


def gen_queryfrag(r):
    q = r.choice(["", "?", "?a=b", "?a=b&c=d", "?x y", "?a=1&b=2&c=3",
                  "?q=%d" % r.randint(0, 999), "?%s" % r.choice(["k=v", "flag", "a[]=1"])])
    f = r.choice(["", "#", "#frag", "#a b", "#x#y", "#sec%d" % r.randint(0, 99),
                  "#%s" % r.choice(["top", "a=b", "L12"])])
    return "http://h/path%s%s" % (q, f), None


def gen_relative(r):
    base = r.choice(BASES)
    rel = r.choice([
        "g", "./g", "../g", "../../g", "/g", "//g", "?y", "#s", "",
        "g?y", "g#s", ".", "..", "../", "g/", "../..", "http:g",
        "https://other/x", "a/b/c", "../../../g", "/./g", "g:h",
    ])
    return rel, base


def gen_encoding(r):
    specials = [" ", chr(34), "<", ">", "`", "{", "}", "|", "\\", "^",
                "é", "ñ", "€", "	", "%zz", "%20", "%2e",
                "%41", "'", "[", "]"]
    tok = "".join(r.choice(specials) for _ in range(r.randint(1, 4)))
    comp = r.choice(["path", "query", "frag", "user"])
    if comp == "path":
        return "http://h/a%sb" % tok, None
    if comp == "query":
        return "http://h/p?x=%s" % tok, None
    if comp == "frag":
        return "http://h/p#%s" % tok, None
    return "http://%s@h/" % tok.replace("\\", ""), None


def gen_errors(r):
    fixed = [
        "http://", "http://:80/", "http://user@/", "http://h:99999/",
        "http://h:port/", "http://[::/", "http://[::1", "https://",
        "http:// /", "http://a b/", "foo", "//h/p", "http://[1::2::3]/",
        "http://[:::]/", "http://h]/", "ws://", "ftp://", "http://[]/",
        "http://[gggg::]/", "http://h:-1/", "http://[12345::]/",
    ]
    style = r.randint(0, 2)
    if style == 0:
        return r.choice(fixed), None
    if style == 1:
        return "http://[%s]/" % (":".join("%x" % r.randint(0, 0xFFFF)
                                          for _ in range(r.randint(9, 12)))), None
    return "http://h:%d/" % r.randint(70000, 999999), None


BUILDERS = {
    "scheme": gen_scheme, "authority": gen_authority, "host_domain": gen_host_domain,
    "host_ipv4": gen_host_ipv4, "host_ipv6": gen_host_ipv6, "port": gen_port,
    "path": gen_path, "opaque": gen_opaque, "queryfrag": gen_queryfrag,
    "relative": gen_relative, "encoding": gen_encoding, "errors": gen_errors,
}

PER_CATEGORY = {
    "scheme": 120, "authority": 140, "host_domain": 90, "host_ipv4": 140,
    "host_ipv6": 130, "port": 60, "path": 120, "opaque": 90, "queryfrag": 90,
    "relative": 160, "encoding": 130, "errors": 90,
}


def generate(out_dir):
    r = random.Random(SEED)
    manifest = []
    seen = set()
    for cat, count in PER_CATEGORY.items():
        builder = BUILDERS[cat]
        made = 0
        attempts = 0
        while made < count and attempts < count * 60:
            attempts += 1
            inp, base = builder(r)
            key = json.dumps([inp, base], ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            cid = "%s_%04d" % (cat, made)
            cdir = os.path.join(out_dir, cid)
            os.makedirs(cdir, exist_ok=True)
            with open(os.path.join(cdir, "input.json"), "w", encoding="utf-8") as f:
                json.dump({"input": inp, "base": base}, f, ensure_ascii=False)
            manifest.append({"id": cid, "category": cat,
                             "weight": CATEGORIES[cat], "entry": "input.json"})
            made += 1
    with open(os.path.join(out_dir, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "candidates_url"
    os.makedirs(out, exist_ok=True)
    m = generate(out)
    counts = {}
    for c in m:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    print("generated %d candidates into %s" % (len(m), out))
    for cat in CATEGORIES:
        print("  %-12s %d" % (cat, counts.get(cat, 0)))
