"""Build the submission zip with correct Unix file modes.

Windows tar/zip tools store every file as non-executable (0666), so a harness
that launches the verifier as `./test.sh` (relying on the exec bit) silently
fails to run it. This builder writes the archive with explicit modes: 0755 for
*.sh, 0644 for everything else, forward-slash paths, a fixed 2021-01-01
timestamp, and no __pycache__/*.pyc. task.toml sits at the archive root.

    python3 authoring/make_zip.py            # -> corgi-bundle.zip
"""
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "bundle")
OUT = os.path.join(REPO, "corgi-bundle.zip")
FIXED_DATE = (2021, 1, 1, 0, 0, 0)

TOP_LEVEL = ["task.toml", "instruction.md", "job.yaml", "oracle.yaml",
             "environment", "solution", "tests"]


def iter_files():
    for top in TOP_LEVEL:
        p = os.path.join(BUNDLE, top)
        if os.path.isfile(p):
            yield p
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in sorted(files):
                if fn.endswith(".pyc"):
                    continue
                yield os.path.join(root, fn)


def main():
    if os.path.exists(OUT):
        os.remove(OUT)
    n = 0
    exec_n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in iter_files():
            arc = os.path.relpath(path, BUNDLE).replace(os.sep, "/")
            with open(path, "rb") as f:
                data = f.read()
            zi = zipfile.ZipInfo(arc, date_time=FIXED_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            is_sh = arc.endswith(".sh")
            mode = 0o755 if is_sh else 0o644
            zi.external_attr = (mode & 0xFFFF) << 16
            z.writestr(zi, data)
            n += 1
            if is_sh:
                exec_n += 1
    print("wrote %s" % OUT)
    print("  %d files, %d executable (.sh)" % (n, exec_n))
    # verify
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        assert "task.toml" in names, "task.toml not at root"
        assert not any("__pycache__" in x or x.endswith(".pyc") for x in names), "pycache leaked"
        for zi in z.infolist():
            if zi.filename.endswith(".sh"):
                perm = (zi.external_attr >> 16) & 0o777
                print("  exec: %s mode=%o" % (zi.filename, perm))
    print("  total entries: %d" % len(names))


if __name__ == "__main__":
    main()
