"""Deterministic candidate-case generator for the preprocessor task.

Emits a categorised corpus of C source snippets exercising every difficulty
lever. Generation is seeded so the corpus is byte-for-byte reproducible on the
Docker freeze machine. This script only *generates*; freeze.py runs the
reference + gcc cross-check and decides which candidates survive.

Cases avoid corners where gcc's behaviour is dialect-sensitive or undefined
(trigraphs, digraph operators, __DATE__/__TIME__, high/multi-char constants in
#if), so the gcc-agreement yield stays high.
"""
import json
import os
import random
import sys

SEED = 0x5EED2A

# category -> weight used by the reward.
CATEGORIES = {
    "tokenize": 1.0,
    "object_macro": 1.0,
    "func_macro": 1.5,
    "stringize": 1.0,
    "paste": 1.5,
    "variadic": 1.0,
    "conditional": 1.5,
    "include": 1.0,
    "builtins": 1.0,
    "integration": 2.0,
    "errors": 1.0,
}

IDENTS = ["foo", "bar", "baz", "qux", "x", "y", "z", "a", "b", "c", "n", "m",
          "val", "tmp", "item", "node", "acc", "buf", "idx", "k"]
NUMS = ["0", "1", "2", "3", "7", "42", "100", "0x1f", "010", "1000000"]
PUNCT_SEQ = ["+", "-", "*", "/", "%", "==", "!=", "<=", ">=", "<<", ">>",
             "&&", "||", "->", "++", "--", "+=", "-=", "?", ":", ";", ",",
             "(", ")", "[", "]", "{", "}", ".", "&", "|", "^", "~", "!"]


def rid(r):
    return r.choice(IDENTS)


def rnum(r):
    return r.choice(NUMS)


# ---------------------------------------------------------------------------
# Per-category generators. Each returns {"entry", "files"}.
# ---------------------------------------------------------------------------

def gen_tokenize(r):
    kinds = []
    n = r.randint(3, 9)
    ppnums = ["1e+5", "0x1p-3", "1.0f", "3.14", ".5", "0xABCp+2", "100ULL",
              "0b1010" if False else "0777", "1'000" if False else "12345"]
    strs = ['"hello"', r'"a\tb\n"', '"quote\\"here"', 'L"wide"', 'u8"utf"']
    chrs = ["'a'", r"'\n'", "'0'", r"'\\'", "L'x'"]
    body = []
    for _ in range(n):
        pick = r.random()
        if pick < 0.3:
            body.append(r.choice(ppnums))
        elif pick < 0.5:
            body.append(r.choice(strs))
        elif pick < 0.62:
            body.append(r.choice(chrs))
        elif pick < 0.85:
            body.append(r.choice(PUNCT_SEQ))
        else:
            body.append(rid(r))
    # Occasionally insert a comment or a line splice.
    src = " ".join(body)
    if r.random() < 0.3:
        src = src.replace(" ", " /*c*/ ", 1)
    if r.random() < 0.3:
        parts = src.split(" ", 2)
        if len(parts) >= 2:
            src = parts[0] + "\\\n" + " ".join(parts[1:])
    return {"entry": "main.c", "files": {"main.c": src + "\n"}}


def gen_object_macro(r):
    lines = []
    names = ["A", "B", "C", "D", "E"]
    r.shuffle(names)
    # A small define chain.
    depth = r.randint(1, 4)
    for i in range(depth):
        if i == depth - 1:
            lines.append("#define %s %s" % (names[i], rnum(r)))
        else:
            lines.append("#define %s %s" % (names[i], names[i + 1]))
    use = names[0]
    tail = []
    if r.random() < 0.4:
        # add a self-referential macro that must not loop
        lines.append("#define S S %s" % rnum(r))
        tail.append("S")
    body = use + (" " + " ".join(tail) if tail else "")
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n" + body + "\n"}}


def gen_func_macro(r):
    lines = []
    style = r.randint(0, 3)
    if style == 0:
        lines.append("#define SQ(x) ((x)*(x))")
        lines.append("#define N %s" % rnum(r))
        body = "SQ(N)"
    elif style == 1:
        lines.append("#define MAX(a,b) ((a)>(b)?(a):(b))")
        body = "MAX(%s, %s)" % (rnum(r), rnum(r))
    elif style == 2:
        lines.append("#define APPLY(f,x) f(x)")
        lines.append("#define INC(n) ((n)+1)")
        body = "APPLY(INC, %s)" % rnum(r)
    else:
        lines.append("#define ID(x) x")
        body = "ID((%s, %s))" % (rid(r), rnum(r))
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n" + body + "\n"}}


def gen_stringize(r):
    def rand_arg():
        toks = []
        for _ in range(r.randint(1, 5)):
            p = r.random()
            if p < 0.3:
                toks.append(rid(r))
            elif p < 0.55:
                toks.append(rnum(r))
            elif p < 0.72:
                # No bare commas or parens: those would split/unbalance the
                # single macro argument rather than exercise stringization.
                toks.append(r.choice(["+", "-", "*", "==", "->", "<<", "!", "~"]))
            elif p < 0.85:
                toks.append(r.choice(['"s"', r'"a\tb"', r"'\n'", "'x'"]))
            else:
                toks.append(rid(r) + "/*c*/" + rid(r))
        sep = r.choice([" ", "  ", "   "])
        return sep.join(toks)

    arg = rand_arg()
    lines = ["#define STR(x) #x", "#define XSTR(x) STR(x)"]
    style = r.randint(0, 2)
    if style == 0:
        lines.append("#define VAL %s" % rnum(r))
        body = "XSTR(VAL)"
    elif style == 1:
        body = "STR(%s)" % arg
    else:
        lines.append("#define PAIR(a,b) #a #b")
        body = "PAIR(%s, %s)" % (rand_arg(), rand_arg())
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n" + body + "\n"}}


def gen_paste(r):
    style = r.randint(0, 4)
    if style == 0:
        lines = ["#define CAT(a,b) a##b"]
        body = "CAT(%s,%s)" % (rid(r), rnum(r))
    elif style == 1:
        lines = ["#define CAT(a,b) a##b", "#define %s%s 123" % ("pre", "fix")]
        body = "CAT(pre,fix)"
    elif style == 2:
        lines = ["#define CAT3(a,b,c) a##b##c"]
        body = "CAT3(%s,_,%s)" % (rid(r), rid(r))
    elif style == 3:
        lines = ["#define CAT(a,b) a##b"]
        body = "CAT(,%s) CAT(%s,)" % (rid(r), rid(r))
    else:
        lines = ["#define GLUE(a,b) a##b", "#define AB 99"]
        body = "GLUE(A,B)"
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n" + body + "\n"}}


def gen_variadic(r):
    style = r.randint(0, 3)
    if style == 0:
        lines = ["#define LOG(...) f(__VA_ARGS__)"]
        args = ", ".join(rnum(r) for _ in range(r.randint(1, 4)))
        body = "LOG(%s)" % args
    elif style == 1:
        lines = ["#define LOG(fmt,...) g(fmt, ##__VA_ARGS__)"]
        if r.random() < 0.5:
            body = 'LOG("m")'
        else:
            body = 'LOG("m", %s, %s)' % (rnum(r), rnum(r))
    elif style == 2:
        lines = ["#define COUNT(...) NARG(__VA_ARGS__, 3, 2, 1, 0)",
                 "#define NARG(a,b,c,d,n,...) n"]
        body = "COUNT(x, y)"
    else:
        lines = ["#define FIRST(a, ...) a"]
        body = "FIRST(%s, %s, %s)" % (rnum(r), rnum(r), rnum(r))
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n" + body + "\n"}}


def gen_conditional(r):
    style = r.randint(0, 5)
    if style == 0:
        e = "%s %s %s" % (rnum(r), r.choice(["+", "-", "*", "<<", "|", "&"]), rnum(r))
        lines = ["#if %s" % e, "T", "#else", "F", "#endif"]
    elif style == 1:
        lines = ["#define V %s" % rnum(r),
                 "#if defined(V) && V > 1", "big", "#elif defined(V)", "small",
                 "#else", "none", "#endif"]
    elif style == 2:
        lines = ["#if 1 ? %s : %s" % (rnum(r), rnum(r)), "y", "#endif"]
    elif style == 3:
        lines = ["#ifdef NOPE", "a", "#else",
                 "#if %s %s %s" % (rnum(r), r.choice(["==", "!=", "<", ">"]), rnum(r)),
                 "b", "#else", "c", "#endif", "#endif"]
    elif style == 4:
        lines = ["#if 'A' == 65 && '0' == 48", "ascii", "#endif"]
    else:
        lines = ["#if (1u - 2) > 0", "wrap", "#else", "nowrap", "#endif"]
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n"}}


def gen_include(r):
    style = r.randint(0, 2)
    if style == 0:
        hdr = "#define FROM_HDR %s\n" % rnum(r)
        main = '#include "h.h"\nFROM_HDR\n'
        return {"entry": "main.c", "files": {"main.c": main, "h.h": hdr}}
    if style == 1:
        guard = ("#ifndef G_H\n#define G_H\n#define GV %s\n#endif\n" % rnum(r))
        main = '#include "g.h"\n#include "g.h"\nGV\n'
        return {"entry": "main.c", "files": {"main.c": main, "g.h": guard}}
    # nested include
    a = '#include "b.h"\n#define A_V %s\n' % rnum(r)
    b = "#define B_V %s\n" % rnum(r)
    main = '#include "a.h"\nA_V B_V\n'
    return {"entry": "main.c", "files": {"main.c": main, "a.h": a, "b.h": b}}


def gen_builtins(r):
    style = r.randint(0, 4)
    if style == 0:
        parts = []
        for _ in range(r.randint(2, 6)):
            parts.append("\n" * r.randint(0, 3))
            parts.append("__LINE__\n")
        src = "".join(parts)
    elif style == 1:
        name = r.choice(["WHERE", "HERE", "L", "POS", "AT"])
        gap = "\n" * r.randint(1, 4)
        src = "#define %s __LINE__\n%s%s%s\n" % (name, name, gap, name)
    elif style == 2:
        n = r.randint(2, 5)
        src = " ".join(["__COUNTER__"] * n) + "\n"
    elif style == 3:
        # __LINE__ carried through a function-like macro.
        src = ("#define AT(x) x __LINE__\n" + "\n" * r.randint(0, 2) +
               "AT(%s)\nAT(%s)\n" % (rid(r), rnum(r)))
    else:
        # splice shifts physical lines, so __LINE__ jumps.
        src = "__LINE__\nabc \\\ndef __LINE__\n__LINE__\n"
    return {"entry": "main.c", "files": {"main.c": src}}


def gen_integration(r):
    # Combine several features into one longer program.
    lines = [
        "#define STR(x) #x",
        "#define XSTR(x) STR(x)",
        "#define CAT(a,b) a##b",
        "#define MAX(a,b) ((a)>(b)?(a):(b))",
        "#define VERSION %s" % rnum(r),
        "#define NAME(n) CAT(sym_, n)",
        "#if VERSION >= 1",
        "int NAME(%s) = MAX(%s, %s);" % (rid(r), rnum(r), rnum(r)),
        "const char* v = XSTR(VERSION);",
        "#else",
        "int NAME(fallback);",
        "#endif",
        "#define APPLY(f, ...) f(__VA_ARGS__)",
        "APPLY(callback, %s, %s)" % (rnum(r), rid(r)),
    ]
    return {"entry": "main.c", "files": {"main.c": "\n".join(lines) + "\n"}}


def gen_errors(r):
    style = r.randint(0, 7)
    if style == 0:
        src = "#if %s\nx\n" % rnum(r)               # unterminated #if
    elif style == 1:
        src = "#error something went wrong\n"        # #error
    elif style == 2:
        # Pairs that cannot merge into one valid pp-token.
        a, b = r.choice([("/", "/"), (".", "."), ("&", "|"), ("<", ">"), ("%", "%")])
        src = "#define C(a,b) a##b\nC(%s,%s)\n" % (a, b)  # invalid paste
    elif style == 3:
        src = "#define F(a,b) a b\nF(%s\n" % rnum(r)  # unterminated macro call
    elif style == 4:
        src = "#if %s/0\ny\n#endif\n" % rnum(r)       # division by zero
    elif style == 5:
        src = "#if %s.5\ny\n#endif\n" % rnum(r)       # float in #if
    elif style == 6:
        src = "#endif\n"                               # stray #endif
    else:
        src = "#if 0\n#else\n#else\nx\n#endif\n"       # #else after #else
    return {"entry": "main.c", "files": {"main.c": src}}


BUILDERS = {
    "tokenize": gen_tokenize,
    "errors": gen_errors,
    "object_macro": gen_object_macro,
    "func_macro": gen_func_macro,
    "stringize": gen_stringize,
    "paste": gen_paste,
    "variadic": gen_variadic,
    "conditional": gen_conditional,
    "include": gen_include,
    "builtins": gen_builtins,
    "integration": gen_integration,
}

# How many candidates to generate per category before cross-check filtering.
PER_CATEGORY = {
    "tokenize": 160,
    "object_macro": 120,
    "func_macro": 140,
    "stringize": 100,
    "paste": 140,
    "variadic": 120,
    "conditional": 160,
    "include": 90,
    "builtins": 70,
    "integration": 120,
    "errors": 64,
}


def generate(out_dir):
    r = random.Random(SEED)
    manifest = []
    seen = set()
    for cat, count in PER_CATEGORY.items():
        builder = BUILDERS[cat]
        made = 0
        attempts = 0
        while made < count and attempts < count * 40:
            attempts += 1
            case = builder(r)
            key = json.dumps(case["files"], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            cid = "%s_%04d" % (cat, made)
            cdir = os.path.join(out_dir, cid)
            os.makedirs(cdir, exist_ok=True)
            for fname, content in case["files"].items():
                # Write bytes with LF and exactly one trailing newline so the
                # frozen corpus is byte-clean on any OS (no CRLF, no missing EOL).
                content = content.replace("\r\n", "\n").replace("\r", "\n")
                if not content.endswith("\n"):
                    content += "\n"
                open(os.path.join(cdir, fname), "wb").write(content.encode("utf-8"))
            manifest.append({
                "id": cid,
                "category": cat,
                "weight": CATEGORIES[cat],
                "entry": case["entry"],
            })
            made += 1
    with open(os.path.join(out_dir, "candidates.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    os.makedirs(out, exist_ok=True)
    m = generate(out)
    counts = {}
    for c in m:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    print("generated %d candidate cases into %s" % (len(m), out))
    for cat in CATEGORIES:
        print("  %-14s %d" % (cat, counts.get(cat, 0)))
