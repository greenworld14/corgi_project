# Validation & submission runbook (URL-parser task)

`authoring/` is tooling and is NOT part of the submitted zip. Only `bundle/`
ships.

## What is already done (authored + locally checked)

- Reference WHATWG URL parser `bundle/solution/ref/urlp` — matches Node's `URL`
  on the whole generated corpus (`authoring/url_difftest.py`, `freeze_url.py`
  reports `drop_disagree 0`).
- Case generator + Node cross-check freeze (`authoring/gen_cases_url.py`,
  `authoring/freeze_url.py`, `authoring/url_oracle_batch.js`). The frozen,
  Node-validated corpus is already in `bundle/tests/hidden/` and
  `bundle/environment/cases/visible/`.
- Sealed verifier `bundle/tests/` — reference scores **1.0000**, stub scores
  **0.0000** (`authoring/test_verifier.py`), well under the 0.15 floor.
- Stub, `check.py`, `instruction.md`, `docs/CONTRACT.md`, `task.toml`,
  `Dockerfile`, `timer.sh`, `job.yaml`, `oracle.yaml`.

Everything above was validated locally with Node as the oracle, so unlike a
compiler task this needed no Docker to cross-check.

## Re-freeze (only if you change the generator or reference)

Needs Node + python3 (no Docker required):

```bash
python3 authoring/gen_cases_url.py authoring/candidates_url
python3 authoring/freeze_url.py \
  --candidates authoring/candidates_url \
  --ref-dir bundle/solution/ref \
  --out-hidden bundle/tests/hidden \
  --out-visible bundle/environment/cases/visible \
  --node node
```

Confirm `drop_disagree` stays at/near 0 and every category keeps a healthy
count.

## Full local gate check

```bash
python3 authoring/check_all.py     # expect: all gates PASS, 0 WARN
```

## Package (always use this — never a plain zip)

```bash
python3 authoring/make_zip.py      # -> corgi-bundle.zip
```

`make_zip.py` sets executable bits on the `.sh` scripts, fixes every file's
timestamp (so the harness's build-integrity check does not flag freshly written
files), strips `__pycache__`, and puts `task.toml` at the archive root.

## Optional: real harness validation on a Docker machine

```bash
harbor run -p . -a oracle -e docker -k 1   # reference must score ~1.0
harbor run -p . -a nop    -e docker -k 1   # untouched stub must sit at its floor
```
