"""URL record, serializer, and the basic-URL-parser state machine."""

from . import parser as P
from .parser import (URLError, is_special, SPECIAL, pct_encode,
                     _in_fragment, _in_query, _in_special_query, _in_path,
                     _in_userinfo, _is_ascii_alpha, _is_ascii_alnum,
                     _is_ascii_digit, parse_host)

EOF = None

(SCHEME_START, SCHEME, NO_SCHEME, SPECIAL_RELATIVE_OR_AUTHORITY,
 PATH_OR_AUTHORITY, RELATIVE, RELATIVE_SLASH, SPECIAL_AUTHORITY_SLASHES,
 SPECIAL_AUTHORITY_IGNORE_SLASHES, AUTHORITY, HOST, PORT, FILE, FILE_SLASH,
 FILE_HOST, PATH_START, PATH, OPAQUE_PATH, QUERY, FRAGMENT) = range(20)


class URL:
    __slots__ = ("scheme", "username", "password", "host", "port", "path",
                 "query", "fragment", "opaque")

    def __init__(self):
        self.scheme = ""
        self.username = ""
        self.password = ""
        self.host = None
        self.port = None
        self.path = []          # list[str], or str when opaque
        self.query = None
        self.fragment = None
        self.opaque = False

    def is_special(self):
        return is_special(self.scheme)

    def includes_credentials(self):
        return self.username != "" or self.password != ""

    def has_opaque_path(self):
        return self.opaque

    # component views (match the standard URL API)
    def protocol(self):
        return self.scheme + ":"

    def hostname(self):
        return "" if self.host is None else self.host

    def port_str(self):
        return "" if self.port is None else str(self.port)

    def host_str(self):
        h = self.hostname()
        if self.port is not None:
            h += ":" + str(self.port)
        return h

    def pathname(self):
        if self.opaque:
            return self.path
        return "".join("/" + s for s in self.path)

    def search(self):
        # The API getter treats an empty query like a null one, even though the
        # serialized href still carries the "?".
        return "" if not self.query else "?" + self.query

    def hash(self):
        return "" if not self.fragment else "#" + self.fragment

    def href(self):
        out = self.scheme + ":"
        if self.host is not None:
            out += "//"
            if self.includes_credentials():
                out += self.username
                if self.password != "":
                    out += ":" + self.password
                out += "@"
            out += self.host
            if self.port is not None:
                out += ":" + str(self.port)
        elif (self.host is None and not self.opaque and len(self.path) > 1
              and self.path[0] == ""):
            out += "/."
        out += self.pathname()
        if self.query is not None:
            out += "?" + self.query
        if self.fragment is not None:
            out += "#" + self.fragment
        return out


def _strip_c0_space(s):
    i, j = 0, len(s)
    while i < j and (ord(s[i]) <= 0x20):
        i += 1
    while j > i and (ord(s[j - 1]) <= 0x20):
        j -= 1
    return s[i:j]


_TABNL = {0x09: None, 0x0A: None, 0x0D: None}


def _shorten_path(url):
    path = url.path
    if not path:
        return
    if url.scheme == "file" and len(path) == 1 and _is_windows_drive(path[0], True):
        return
    path.pop()


def _is_windows_drive(s, normalized=False):
    if len(s) != 2:
        return False
    if not _is_ascii_alpha(s[0]):
        return False
    if normalized:
        return s[1] == ":"
    return s[1] in ":|"


def _starts_with_windows_drive(s):
    if len(s) < 2:
        return False
    if not (_is_ascii_alpha(s[0]) and s[1] in ":|"):
        return False
    if len(s) == 2:
        return True
    return s[2] in "/\\?#"


def parse(inp, base=None):
    url = URL()
    inp = _strip_c0_space(inp)
    inp = inp.translate(_TABNL)

    state = SCHEME_START
    buffer = ""
    at_seen = False
    inside_brackets = False
    password_token_seen = False
    ptr = 0
    L = len(inp)

    def C(p):
        return inp[p] if 0 <= p < L else EOF

    while ptr <= L:
        c = C(ptr)

        if state == SCHEME_START:
            if c is not EOF and _is_ascii_alpha(c):
                buffer += c.lower()
                state = SCHEME
            else:
                state = NO_SCHEME
                ptr -= 1

        elif state == SCHEME:
            if c is not EOF and (_is_ascii_alnum(c) or c in "+-."):
                buffer += c.lower()
            elif c == ":":
                url.scheme = buffer
                buffer = ""
                if url.scheme == "file":
                    state = FILE
                elif url.is_special() and base is not None and base.scheme == url.scheme:
                    state = SPECIAL_RELATIVE_OR_AUTHORITY
                elif url.is_special():
                    state = SPECIAL_AUTHORITY_SLASHES
                elif C(ptr + 1) == "/":
                    state = PATH_OR_AUTHORITY
                    ptr += 1
                else:
                    url.opaque = True
                    url.path = ""
                    state = OPAQUE_PATH
            else:
                buffer = ""
                state = NO_SCHEME
                ptr = -1  # restart from 0
        elif state == NO_SCHEME:
            if base is None or (base.has_opaque_path() and c != "#"):
                raise URLError("missing scheme")
            if base.has_opaque_path() and c == "#":
                url.scheme = base.scheme
                url.path = base.path
                url.opaque = True
                url.query = base.query
                url.fragment = ""
                state = FRAGMENT
            elif base.scheme != "file":
                state = RELATIVE
                ptr -= 1
            else:
                state = FILE
                ptr -= 1

        elif state == SPECIAL_RELATIVE_OR_AUTHORITY:
            if c == "/" and C(ptr + 1) == "/":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                ptr += 1
            else:
                state = RELATIVE
                ptr -= 1

        elif state == PATH_OR_AUTHORITY:
            if c == "/":
                state = AUTHORITY
            else:
                state = PATH
                ptr -= 1

        elif state == RELATIVE:
            url.scheme = base.scheme
            if c == "/":
                state = RELATIVE_SLASH
            elif url.is_special() and c == "\\":
                state = RELATIVE_SLASH
            else:
                url.username = base.username
                url.password = base.password
                url.host = base.host
                url.port = base.port
                url.path = list(base.path)
                url.query = base.query
                if c == "?":
                    url.query = ""
                    state = QUERY
                elif c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                elif c is not EOF:
                    url.query = None
                    _shorten_path(url)
                    state = PATH
                    ptr -= 1

        elif state == RELATIVE_SLASH:
            if url.is_special() and c in "/\\":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
            elif c == "/":
                state = AUTHORITY
            else:
                url.username = base.username
                url.password = base.password
                url.host = base.host
                url.port = base.port
                state = PATH
                ptr -= 1

        elif state == SPECIAL_AUTHORITY_SLASHES:
            if c == "/" and C(ptr + 1) == "/":
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                ptr += 1
            else:
                state = SPECIAL_AUTHORITY_IGNORE_SLASHES
                ptr -= 1

        elif state == SPECIAL_AUTHORITY_IGNORE_SLASHES:
            if c not in ("/", "\\"):
                state = AUTHORITY
                ptr -= 1

        elif state == AUTHORITY:
            if c == "@":
                if at_seen:
                    buffer = "%40" + buffer
                at_seen = True
                for ch in buffer:
                    if ch == ":" and not password_token_seen:
                        password_token_seen = True
                        continue
                    enc = pct_encode(ch, _in_userinfo)
                    if password_token_seen:
                        url.password += enc
                    else:
                        url.username += enc
                buffer = ""
            elif c is EOF or c in "/?#" or (url.is_special() and c == "\\"):
                if at_seen and buffer == "":
                    raise URLError("empty host with credentials")
                ptr -= len(buffer) + 1
                buffer = ""
                state = HOST
            else:
                buffer += c

        elif state == HOST:
            if c == ":" and not inside_brackets:
                if buffer == "":
                    raise URLError("empty host")
                url.host = parse_host(buffer, url.is_special())
                buffer = ""
                state = PORT
            elif c is EOF or c in "/?#" or (url.is_special() and c == "\\"):
                ptr -= 1
                if url.is_special() and buffer == "":
                    raise URLError("empty special host")
                url.host = parse_host(buffer, url.is_special())
                buffer = ""
                state = PATH_START
            else:
                if c == "[":
                    inside_brackets = True
                elif c == "]":
                    inside_brackets = False
                buffer += c

        elif state == PORT:
            if c is not EOF and _is_ascii_digit(c):
                buffer += c
            elif c is EOF or c in "/?#" or (url.is_special() and c == "\\"):
                if buffer != "":
                    port = int(buffer)
                    if port > 65535:
                        raise URLError("port out of range")
                    if SPECIAL.get(url.scheme) == port:
                        url.port = None
                    else:
                        url.port = port
                    buffer = ""
                state = PATH_START
                ptr -= 1
            else:
                raise URLError("invalid port char")

        elif state == FILE:
            url.scheme = "file"
            url.host = ""
            if c in ("/", "\\"):
                state = FILE_SLASH
            elif base is not None and base.scheme == "file":
                url.host = base.host
                url.path = list(base.path)
                url.query = base.query
                if c == "?":
                    url.query = ""
                    state = QUERY
                elif c == "#":
                    url.fragment = ""
                    state = FRAGMENT
                elif c is not EOF:
                    url.query = None
                    if not _starts_with_windows_drive(inp[ptr:]):
                        _shorten_path(url)
                    else:
                        url.path = []
                    state = PATH
                    ptr -= 1
            else:
                state = PATH
                ptr -= 1

        elif state == FILE_SLASH:
            if c in ("/", "\\"):
                state = FILE_HOST
            else:
                if base is not None and base.scheme == "file":
                    url.host = base.host
                    if (not _starts_with_windows_drive(inp[ptr:])
                            and len(base.path) > 0
                            and _is_windows_drive(base.path[0], True)):
                        url.path.append(base.path[0])
                state = PATH
                ptr -= 1

        elif state == FILE_HOST:
            if c is EOF or c in "/\\?#":
                ptr -= 1
                if _is_windows_drive(buffer):
                    state = PATH
                elif buffer == "":
                    url.host = ""
                    state = PATH_START
                else:
                    host = parse_host(buffer, True)
                    if host == "localhost":
                        host = ""
                    url.host = host
                    buffer = ""
                    state = PATH_START
            else:
                buffer += c

        elif state == PATH_START:
            if url.is_special():
                state = PATH
                if c not in ("/", "\\"):
                    ptr -= 1
            elif c == "?":
                url.query = ""
                state = QUERY
            elif c == "#":
                url.fragment = ""
                state = FRAGMENT
            elif c is not EOF:
                state = PATH
                if c != "/":
                    ptr -= 1

        elif state == PATH:
            if (c is EOF or c == "/" or (url.is_special() and c == "\\")
                    or c in "?#"):
                if _is_double_dot(buffer):
                    _shorten_path(url)
                    if not (c == "/" or (url.is_special() and c == "\\")):
                        url.path.append("")
                elif _is_single_dot(buffer):
                    if not (c == "/" or (url.is_special() and c == "\\")):
                        url.path.append("")
                else:
                    if (url.scheme == "file" and len(url.path) == 0
                            and _is_windows_drive(buffer)):
                        buffer = buffer[0] + ":"
                    url.path.append(buffer)
                buffer = ""
                if c == "?":
                    url.query = ""
                    state = QUERY
                elif c == "#":
                    url.fragment = ""
                    state = FRAGMENT
            else:
                buffer += pct_encode(c, _in_path)

        elif state == OPAQUE_PATH:
            if c == "?":
                url.query = ""
                state = QUERY
            elif c == "#":
                url.fragment = ""
                state = FRAGMENT
            elif c is not EOF:
                url.path += pct_encode(c, P._c0)

        elif state == QUERY:
            if c is EOF or c == "#":
                enc = _in_special_query if url.is_special() else _in_query
                url.query += pct_encode(buffer, enc)
                buffer = ""
                if c == "#":
                    url.fragment = ""
                    state = FRAGMENT
            else:
                buffer += c

        elif state == FRAGMENT:
            if c is not EOF:
                url.fragment += pct_encode(c, _in_fragment)

        ptr += 1

    return url


def _is_single_dot(b):
    return b == "." or b.lower() == "%2e"


def _is_double_dot(b):
    b = b.lower()
    return b == ".." or b in ("%2e.", ".%2e", "%2e%2e")
