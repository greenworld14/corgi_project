"""Command-line entry point for the URL parser.

    python3 -m urlp <case.json>

Contract (see /app/docs/CONTRACT.md for the full specification):
  * The case file is JSON: {"input": "<string>", "base": "<string>"|null}.
  * On success, print ONE JSON object {"url": {...components...}} to stdout and
    exit 0.
  * If the input (or a supplied base) fails to parse, exit non-zero. stdout is
    ignored on failure.

This stub does no real parsing yet: it reads the file and prints an empty
component set. Replace `parse_url` with a real implementation.
"""
import json
import sys

FIELDS = ["href", "protocol", "username", "password", "host", "hostname",
          "port", "pathname", "search", "hash"]


def parse_url(inp, base):
    """Return a dict of URL components, or raise ValueError on parse failure.

    TODO: implement the WHATWG URL parser. Right now this returns empty
    components so the program is well-formed but scores at the floor.
    """
    return {k: "" for k in FIELDS}


def main(argv):
    if not argv:
        sys.stderr.write("usage: python3 -m urlp <case.json>\n")
        return 2
    with open(argv[0], "r", encoding="utf-8") as f:
        case = json.load(f)
    try:
        url = parse_url(case.get("input", ""), case.get("base"))
    except Exception as e:  # noqa: BLE001 - stub-level catch-all
        sys.stderr.write("error: %s\n" % e)
        return 1
    sys.stdout.write(json.dumps({"url": url}, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
