"""CLI: python3 -m urlp <case.json>

The case file is JSON: {"input": "<string>", "base": "<string>"|null}.
On success, print {"url": {href, protocol, username, password, host, hostname,
port, pathname, search, hash}} and exit 0. If the input (or a supplied base)
fails to parse, exit non-zero with no stdout.
"""
import json
import sys

from .machine import parse
from .parser import URLError


def components(u):
    return {
        "href": u.href(),
        "protocol": u.protocol(),
        "username": u.username,
        "password": u.password,
        "host": u.host_str(),
        "hostname": u.hostname(),
        "port": u.port_str(),
        "pathname": u.pathname(),
        "search": u.search(),
        "hash": u.hash(),
    }


def main(argv):
    if not argv:
        sys.stderr.write("usage: python3 -m urlp <case.json>\n")
        return 2
    with open(argv[0], "r", encoding="utf-8") as f:
        case = json.load(f)
    inp = case.get("input", "")
    base = case.get("base")
    try:
        base_url = parse(base) if base is not None else None
        if base is not None and base_url.scheme == "" :
            return 1
        url = parse(inp, base_url)
        # A URL must have a scheme; otherwise parsing failed to produce one.
        if url.scheme == "":
            return 1
    except URLError:
        return 1
    except Exception as e:  # defensive: any internal error is a parse failure
        sys.stderr.write("error: %s\n" % e)
        return 1
    sys.stdout.write(json.dumps({"url": components(url)}, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    sys.exit(main(sys.argv[1:]))
