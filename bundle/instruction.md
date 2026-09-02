# Build a WHATWG URL parser

You are working in `/app`. Your job is to implement a URL parser that conforms
to the WHATWG URL Standard's *basic URL parser*, from scratch, in Python 3
(standard library only). A stub is already in place; grading is continuous, so a
working partial implementation always scores and a broken tree scores nothing.

## The deliverable

`python3 -m urlp <case-file>` parses one URL and prints its components.

The case file is JSON: `{"input": "<string>", "base": "<string>"|null}`. You must
parse `input` against `base` exactly as `new URL(input, base)` does in a
conforming implementation (and `new URL(input)` when `base` is `null`).


```json
{"url": {
  "href": "http://example.com/a/c",
  "protocol": "http:", "username": "", "password": "",
  "host": "example.com", "hostname": "example.com", "port": "",
  "pathname": "/a/c", "search": "", "hash": ""
}}
```

All ten fields are strings and always present. Their exact meaning — including
the subtle cases (default-port elision, empty query still yielding `search`
`""` while `href` keeps the `?`, IPv4/IPv6 normalization) — is specified in
`/app/docs/CONTRACT.md`. **Read it before you start; it is the specification you
are graded against.**

If the input (or a supplied base) fails to parse, exit non-zero with no stdout.
There is no third option: valid JSON and exit `0`, or a non-zero exit.

## Workspace

```
/app
├── urlp/            the package you edit ("python3 -m urlp")
│   ├── __init__.py
│   └── __main__.py  CLI entry; replace the stub `parse_url`
├── docs/CONTRACT.md the exact output contract — your source of truth
├── cases/visible/   a small sample of cases with expected outputs
└── check.py         local self-check against the visible sample
```

You may restructure the `urlp` package however you like — add modules, rename
internals — as long as `python3 -m urlp <case-file>` keeps the command-line and
JSON contract. Nothing outside `urlp/` needs to change.

## How you are scored

A sealed grader runs your parser against a large hidden set of cases spanning
the whole behavioral surface and reports the **weighted fraction of cases whose
component set exactly matches** the reference. The score is a float in `[0, 1]`,
higher is better. Correctness is a hard gate per case: a case counts only if the
full component set matches (or, for inputs the standard rejects, only if you
exit non-zero). Crashes, timeouts, malformed JSON, and skipped cases all count
as failures against a fixed denominator, so partial progress earns proportional
credit and there is always another case to win.

The hidden set is much larger and broader than the visible sample. Optimize for
the standard's behavior in general, not for the handful of examples you can see.
Categories are weighted (relative resolution, host parsing, and encoding carry
more), so breadth across the surface matters more than polishing one corner.

Estimate your score locally at any time:

```
python3 /app/check.py        # weighted score on the visible sample
python3 /app/check.py -v      # also print each failing case
```

A high visible score is necessary but not sufficient — the hidden set exercises
corners the sample does not.

## What the surface covers

Work through these; each is an independent source of cases:

- **Scheme parsing** — special (`http`, `https`, `ws`, `wss`, `ftp`, `file`) vs
  non-special; case-insensitive scheme; the `://` vs opaque-path split.
- **Authority** — userinfo (`user:pass@`), credentials serialization, the `@`
  and multiple-`@` handling, empty-host detection.
- **Host parsing** — domain lowercasing and forbidden-code-point checks; IPv4
  parsing across decimal, octal (`0…`), and hex (`0x…`) forms and fewer than
  four parts, normalized to dotted-decimal; IPv6 literals in `[...]`, including
  `::` compression and embedded IPv4, re-serialized in canonical compressed
  form; opaque-host parsing for non-special schemes.
- **Ports** — parsing, range checking, and elision of the scheme's default.
- **Paths** — `.`/`..` segment removal; `\` treated as `/` for special schemes;
  multiple slashes; `file:` Windows drive-letter handling.
- **Percent-encoding** — the distinct encode sets for userinfo, path, query,
  special-query, and fragment; preserving existing `%XX`; encoding non-ASCII via
  UTF-8.
- **Query and fragment** — including the empty-vs-null distinction described in
  the contract.
- **Relative resolution** — resolving a reference against a base through the
  relative/authority/path/query/fragment states.

Internationalized domain names (non-ASCII hostnames, punycode) are out of scope
and appear in no case; non-ASCII in the path/query/fragment is in scope and is
percent-encoded.

## Operating rules

Work autonomously until the task ends — never stop to ask a question. Pace
yourself against the task timer rather than the wall clock, which tells you
nothing about your real budget: read `cat /app/.timer/remaining_secs` before any
long run, and watch for `/app/.timer/alert_30min` and `alert_10min` as the
budget winds down. Leave yourself a final pass to confirm the tree still builds
and `python3 -m urlp` still runs on a simple case.

Keep the parser runnable at all times: grading is continuous, so a working
partial implementation always banks points and a broken entry point scores
nothing. Build outward from the cases you already pass — get the common special
schemes and path handling solid before chasing IPv6 edge cases or the rarer
relative-resolution states. When an experiment does not measurably raise your
visible score, revert it and take the next-most-valuable gap. The standard is
deep but fully specified: every remaining failure has a definite right answer in
the contract and the WHATWG algorithm it describes.
