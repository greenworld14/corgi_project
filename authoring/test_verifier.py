"""Run the sealed verifier against the frozen corpus with the reference and the
stub installed, and print the resulting rewards (oracle should be ~1.0, nop
~0.0). Pure-local check; no Docker required.

    python3 authoring/test_verifier.py [--hidden <dir>]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "bundle")
PY = sys.executable
COMPUTE = os.path.join(BUNDLE, "tests", "compute_reward.py")
REF = os.path.join(BUNDLE, "solution", "ref", "urlp")
STUB = os.path.join(BUNDLE, "environment", "urlp")


def run(app_src, hidden):
    with tempfile.TemporaryDirectory() as d:
        app = os.path.join(d, "app")
        verifier = os.path.join(d, "verifier")
        os.makedirs(app)
        os.makedirs(verifier)
        shutil.copytree(app_src, os.path.join(app, "urlp"))
        env = dict(os.environ)
        env["PP_APP_DIR"] = app
        env["PP_HIDDEN_DIR"] = hidden
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.run([PY, COMPUTE], cwd=verifier, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        with open(os.path.join(verifier, "reward.json"), encoding="utf-8") as f:
            return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hidden", default=os.path.join(BUNDLE, "tests", "hidden"))
    args = ap.parse_args()

    ref = run(REF, args.hidden)
    stub = run(STUB, args.hidden)
    print("  reference reward = %.4f  (total weight %s)"
          % (ref["reward"], ref.get("total_weight")))
    print("  stub reward      = %.4f" % stub["reward"])
    ok = ref["reward"] >= 0.95 and stub["reward"] <= 0.15
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
