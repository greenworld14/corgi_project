# Authoring notes — C preprocessor conformance task

**This directory is authoring-only. It is NOT part of the submitted zip.**
Only `bundle/` gets zipped.

## Paradigm

Implementation. Reward = weighted fraction of hidden cases whose emitted pp-token
stream matches the frozen expectation exactly. Stub floor ~0, reference ~1.0.

## Why this subject

- The behavioural surface (C11 translation phases 1–4) is far too large to cover
  by luck, so partial credit is smooth and there is always a next case to win.
- The expectation is generated from a real external artifact (`gcc -E`), not a
  hand-authored test list, so the surface is both the difficulty and a free oracle.
- Grading is exact-match on a token stream: deterministic, fast, no timing noise.

## The central anti-cheat problem

The obvious cheat is shelling out to a system preprocessor. Mitigations, in order
of importance:

1. **No C toolchain in the image at all.** The Dockerfile installs `python3` and
   nothing that ships a preprocessor — no `gcc`, `clang`, `tcc`, `cpp`, no
   `build-essential`. The verifier asserts these are absent before scoring.
2. **Expectations are frozen at authoring time.** Grading never runs `gcc`, so the
   image never needs one. `tests/hidden/` ships input + expected token stream.
3. **Sealed grader.** `tests/` is mounted only at grading time and is unreachable
   from `/app`.
4. **Candidate runs with a scrubbed environment** — empty `PATH`, no
   `PYTHONPATH`/`LD_PRELOAD`, no network, per-case timeout.

Because Python is required in the image anyway (the reward script is
`compute_reward.py`), the implementation language is Python 3, stdlib only.
Requiring a compiled language would drag a C toolchain — and therefore a
preprocessor — back into the image.

## Output contract (the spine)

The candidate emits a **flat JSON list of pp-tokens**; newlines and whitespace are
dropped entirely:

```json
{"tokens": [["id","foo"],["punct","("],["num","1"],["punct",")"]]}
```

Dropping line structure is deliberate. Comparing raw `gcc -E` text is fragile
(line markers, whitespace-to-avoid-pasting, blank-line runs) and would generate
false failures that have nothing to do with preprocessing semantics. A token
stream still tests everything that matters:

- accidental pasting is caught (`+ +` vs `++` are different token lists)
- `#` stringification is caught exactly, because the whitespace rules are baked
  into the resulting string literal's spelling
- `##` pasting is caught, because it produces one token instead of two
- `__LINE__` / `#line` are caught, because they expand to number tokens

Token kinds: `id`, `num`, `chr`, `str`, `punct`, `other`. Header-names never
appear — `#include` is consumed during preprocessing.

## Determinism pins

| Macro | Value | Note |
|---|---|---|
| `__STDC__` | `1` | passed to gcc via `-D` during cross-check |
| `__STDC_VERSION__` | `201112L` | ditto |
| `__STDC_HOSTED__` | `1` | ditto |
| `__FILE__` | the path exactly as passed on the command line | cross-check uses the same relative path |
| `__LINE__` | per C11, affected by `#line` | |
| `__COUNTER__` | starts at 0, increments per expansion | GNU, supported by gcc |
| `__DATE__` / `__TIME__` | pinned constants | **excluded from generated cases** — gcc cannot be pinned to match |

Cross-check invocation:

```
gcc -undef -std=gnu11 -E -P -nostdinc \
    -D__STDC__=1 -D__STDC_VERSION__=201112L -D__STDC_HOSTED__=1 \
    -I<case_dir> <case>.c
```

`-undef` matters: it strips gcc's own predefined macros (`__GNUC__`,
`__x86_64__`, …) so that undefined identifiers evaluate to `0` in `#if` in both
implementations. `-std=gnu11` keeps `,##__VA_ARGS__` (GNU comma deletion) working
while leaving `__STDC_VERSION__` at the C11 value.

`__VA_OPT__` is deliberately **out of scope** — gcc's support for it varies by
`-std` mode and would make the cross-check unstable.

The gcc output is tokenised with the reference tokeniser before comparison. This
validates macro-expansion logic against gcc; tokenisation itself is validated
separately by dedicated phase-3 cases.

## Difficulty levers

The notes warn that single-lever tasks saturate. Independent levers here:

1. Phases 1–2: backslash-newline splicing (including inside tokens and splicing
   that forms a directive). Trigraphs are out of scope: they are disabled in the
   gnu11 dialect the cross-check uses, so generating them would be inconsistent.
2. Phase 3: pp-number grammar (`1.0e+5`, `0x1p-3`, `1e+`), punctuator maximal
   munch (`>>=`, `...`, `<:`/`:>` digraphs), comment removal producing one space
3. Macro expansion: rescanning, blue paint / self-reference suppression,
   argument prescan order, painted tokens surviving into later expansions
4. `#` stringification whitespace and escaping rules
5. `##` pasting: order of evaluation, pasting placemarkers, invalid-paste cases
6. Variadics: `__VA_ARGS__`, empty variadic args, GNU `,##__VA_ARGS__`
7. `#if` evaluation: C integer semantics, `defined()` including the macro-expanded
   form, `/` and `%` by zero guarded by short-circuit, character constants
8. `#include` resolution, nesting, header guards, `#include` with a macro-expanded
   operand
9. `#line` effects on `__LINE__`/`__FILE__`, `_Pragma` destringisation

An agent must get most of these independently right; there is no single trick
that unlocks the score.

## Scoring

Per-case **binary exact match**, category-weighted, fixed denominator. Crashes,
timeouts, malformed JSON and skipped cases all count as failures. Binary rather
than partial-per-case scoring because sequence-similarity credit is gameable by
emitting plausible filler; with ~1000 cases the reward is already smooth.

## Open items

- `job.yaml` / `oracle.yaml` are required by the notes but neither document gives
  a schema. **Must be confirmed before submitting.** See `RUNBOOK.md`.
- The freeze step must run on a machine with Docker + gcc + python3. It cannot
  run on the authoring box (Windows, no toolchain).
