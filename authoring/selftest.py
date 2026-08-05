"""Authoring-time self-test for the reference preprocessor.

Runs the reference on hand-written cases with known-correct expected token
streams (verified against C semantics by hand). This does NOT replace the gcc
cross-check at freeze time; it is a fast local guard against regressions while
authoring on a machine without gcc.
"""
import json
import os
import subprocess
import sys
import tempfile

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "bundle", "solution", "ref")
PY = sys.executable


def run(src, extra=None):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "in.c")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        cmd = [PY, "-m", "pp", p] + (extra or [])
        r = subprocess.run(cmd, cwd=REF_DIR, capture_output=True, text=True)
        return r.returncode, r.stdout.strip(), r.stderr.strip()


def toks(*pairs):
    return {"tokens": [list(p) for p in pairs]}


# Each case: (name, source, expected). expected is a dict for success, or the
# string "ERROR" to require a non-zero exit.
CASES = []


def case(name, src, expected):
    CASES.append((name, src, expected))


# --- object-like + rescanning ---
case("obj-simple", "#define A 42\nA\n", toks(("num", "42")))
case("obj-chain", "#define A B\n#define B C\n#define C 7\nA\n", toks(("num", "7")))
case("self-ref", "#define A A\nA\n", toks(("id", "A")))
case("mutual-ref", "#define A B\n#define B A\nA\n", toks(("id", "A")))
case("indirect-self", "#define f(x) x\n#define g f\ng(g)(2)\n",
     toks(("id", "f"), ("punct", "("), ("num", "2"), ("punct", ")")))

# --- function-like ---
case("func-basic", "#define ADD(a,b) a+b\nADD(1,2)\n",
     toks(("num", "1"), ("punct", "+"), ("num", "2")))
case("func-noexpand-noparen", "#define F(x) x\nF\n", toks(("id", "F")))
case("func-nested-parens", "#define ID(x) x\nID((1,2))\n",
     toks(("punct", "("), ("num", "1"), ("punct", ","), ("num", "2"), ("punct", ")")))
case("arg-prescan", "#define SQ(x) ((x)*(x))\n#define N 3\nSQ(N)\n",
     toks(("punct", "("), ("punct", "("), ("num", "3"), ("punct", ")"),
          ("punct", "*"), ("punct", "("), ("num", "3"), ("punct", ")"),
          ("punct", ")")))

# --- stringize ---
case("str-basic", "#define S(x) #x\nS(a  b)\n", toks(("str", '"a b"')))
case("str-escape", '#define S(x) #x\nS("q\\n")\n', toks(("str", '"\\"q\\\\n\\""')))
case("str-empty", "#define S(x) #x\nS()\n", toks(("str", '""')))

# --- paste ---
case("paste-num", "#define C(a,b) a##b\nC(1,2)\n", toks(("num", "12")))
case("paste-id", "#define C(a,b) a##b\nC(foo,bar)\n", toks(("id", "foobar")))
case("paste-empty-left", "#define C(a,b) a##b\nC(,x)\n", toks(("id", "x")))
case("paste-empty-both", "#define C(a,b) a##b\nC(,)\n", toks())
case("paste-op", "#define C(a,b) a##b\nC(+,+)\n", toks(("punct", "++")))
case("paste-invalid", "#define C(a,b) a##b\nC(+,-)\n", "ERROR")

# --- variadic ---
case("va-basic", "#define P(...) __VA_ARGS__\nP(1,2,3)\n",
     toks(("num", "1"), ("punct", ","), ("num", "2"), ("punct", ","), ("num", "3")))
case("va-named", "#define P(a,...) a: __VA_ARGS__\nP(x,1,2)\n",
     toks(("id", "x"), ("punct", ":"), ("num", "1"), ("punct", ","), ("num", "2")))
case("va-gnu-comma-empty", "#define P(a,...) f(a, ##__VA_ARGS__)\nP(x)\n",
     toks(("id", "f"), ("punct", "("), ("id", "x"), ("punct", ")")))
case("va-gnu-comma-nonempty", "#define P(a,...) f(a, ##__VA_ARGS__)\nP(x,1)\n",
     toks(("id", "f"), ("punct", "("), ("id", "x"), ("punct", ","),
          ("num", "1"), ("punct", ")")))

# --- conditionals ---
case("if-basic", "#if 1+1==2\nyes\n#else\nno\n#endif\n", toks(("id", "yes")))
case("if-defined", "#define X\n#if defined(X)\ny\n#endif\n", toks(("id", "y")))
case("if-undef-zero", "#if UNDEFINED\nno\n#else\ny\n#endif\n", toks(("id", "y")))
case("if-shortcircuit-div", "#if 1 || 1/0\ny\n#endif\n", toks(("id", "y")))
case("if-div0-error", "#if 1/0\nx\n#endif\n", "ERROR")
case("if-elif", "#if 0\na\n#elif 1\nb\n#else\nc\n#endif\n", toks(("id", "b")))
case("if-nested-skip", "#if 0\n#if 1\nx\n#endif\n#else\ny\n#endif\n", toks(("id", "y")))
case("ifdef-false", "#ifdef NOPE\nx\n#endif\n", toks())
case("if-unsigned", "#if -1 > 0u\ny\n#else\nn\n#endif\n", toks(("id", "y")))
case("if-char", "#if 'A' == 65\ny\n#endif\n", toks(("id", "y")))
case("if-ternary", "#if (1 ? 2 : 3) == 2\ny\n#endif\n", toks(("id", "y")))
case("if-float-error", "#if 1.5\nx\n#endif\n", "ERROR")
case("if-unterminated", "#if 1\nx\n", "ERROR")
case("elif-after-else", "#if 0\n#else\n#elif 1\n#endif\n", "ERROR")

# --- builtins ---
case("line-basic", "__LINE__\n__LINE__\n", toks(("num", "1"), ("num", "2")))
case("line-in-macro", "#define L __LINE__\nL\nL\n", toks(("num", "2"), ("num", "3")))
case("counter", "__COUNTER__ __COUNTER__ __COUNTER__\n",
     toks(("num", "0"), ("num", "1"), ("num", "2")))

# --- tokenization ---
case("ppnum-greedy", "1e+5 0x1p-3 1.0f\n",
     toks(("num", "1e+5"), ("num", "0x1p-3"), ("num", "1.0f")))
case("maximal-munch", ">>= ... ->\n",
     toks(("punct", ">>="), ("punct", "..."), ("punct", "->")))
case("no-accidental-paste", "#define E\n1 E +\n",
     toks(("num", "1"), ("punct", "+")))
case("splice-in-token", "in\\\nt x\n",
     toks(("id", "int"), ("id", "x")))
case("comment-space", "a/*c*/b\n", toks(("id", "a"), ("id", "b")))
case("digraph", "<% %> <: :>\n",
     toks(("punct", "<%"), ("punct", "%>"), ("punct", "<:"), ("punct", ":>")))

# --- _Pragma ---
case("pragma-consumed", '_Pragma("once")\nx\n', toks(("id", "x")))

# --- C standard 6.10.3.5 examples (the canonical torture tests) ---
# EXAMPLE 3
case("std-ex3",
     "#define x 3\n"
     "#define f(a) f(x * (a))\n"
     "#undef x\n"
     "#define x 2\n"
     "#define g f\n"
     "#define z z[0]\n"
     "#define h g(~\n"
     "#define m(a) a(w)\n"
     "#define w 0,1\n"
     "#define t(a) a\n"
     "f(y+1) + f(f(z)) % t(t(g)(0) + t)(1);\n",
     toks(("id", "f"), ("punct", "("), ("num", "2"), ("punct", "*"), ("punct", "("),
          ("id", "y"), ("punct", "+"), ("num", "1"), ("punct", ")"), ("punct", ")"),
          ("punct", "+"), ("id", "f"), ("punct", "("), ("num", "2"), ("punct", "*"),
          ("punct", "("), ("id", "f"), ("punct", "("), ("num", "2"), ("punct", "*"),
          ("punct", "("), ("id", "z"), ("punct", "["), ("num", "0"), ("punct", "]"),
          ("punct", ")"), ("punct", ")"), ("punct", ")"), ("punct", ")"), ("punct", "%"),
          ("id", "f"), ("punct", "("), ("num", "2"), ("punct", "*"), ("punct", "("),
          ("num", "0"), ("punct", ")"), ("punct", ")"), ("punct", "+"), ("id", "t"),
          ("punct", "("), ("num", "1"), ("punct", ")"), ("punct", ";")))

# EXAMPLE 4 — stringize and paste
case("std-ex4-hash-hash",
     "#define hash_hash # ## #\n"
     "#define mkstr(a) # a\n"
     "#define in_between(a) mkstr(a)\n"
     "#define join(a, b) in_between(a hash_hash b)\n"
     'join(x, y);\n',
     toks(("str", '"x ## y"'), ("punct", ";")))

# EXAMPLE 5 — variadic
case("std-ex7-debug",
     "#define debug(...) fprintf(stderr, __VA_ARGS__)\n"
     'debug("Flag");\n',
     toks(("id", "fprintf"), ("punct", "("), ("id", "stderr"), ("punct", ","),
          ("str", '"Flag"'), ("punct", ")"), ("punct", ";")))

# rescan re-forms a call that spans the boundary
case("rescan-reform-call",
     "#define lparen (\n#define g(x) x+1\n#define f g lparen 5 )\nf\n",
     toks(("id", "g"), ("punct", "("), ("num", "5"), ("punct", ")")))

# paste then rescan expands the pasted identifier
case("paste-then-rescan",
     "#define AB 99\n#define C(a,b) a##b\nC(A,B)\n",
     toks(("num", "99")))

# blue paint survives pasting: pasted name equal to a macro still not re-expanded
# here the paste forms a fresh token so it DOES expand — contrast with self-ref
case("recursive-func-paint",
     "#define f(x) x f\nf(1)(2)\n",
     toks(("num", "1"), ("id", "f"), ("punct", "("), ("num", "2"), ("punct", ")")))


def main():
    passed = 0
    failed = 0
    for name, src, expected in CASES:
        rc, out, err = run(src)
        if expected == "ERROR":
            ok = rc != 0
            got = "exit=%d" % rc
            want = "non-zero exit"
        else:
            ok = False
            got = out
            want = json.dumps(expected, ensure_ascii=False)
            if rc == 0:
                try:
                    ok = json.loads(out) == expected
                except Exception:
                    ok = False
        if ok:
            passed += 1
        else:
            failed += 1
            print("FAIL %-22s" % name)
            print("   src : %r" % src)
            print("   want: %s" % want)
            print("   got : %s%s" % (got, ("  [stderr: %s]" % err) if err else ""))
    print("\n%d passed, %d failed, %d total" % (passed, failed, passed + failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
