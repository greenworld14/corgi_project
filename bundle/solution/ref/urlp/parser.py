"""WHATWG URL Standard basic URL parser (stdlib only).

Implements enough of https://url.spec.whatwg.org/ to match a conforming
implementation on ASCII inputs: the parser state machine, host parsing
(IPv6/IPv4/opaque/domain), the percent-encode sets, dot-segment removal and
relative resolution. Internationalized domain names (IDNA/punycode) are out of
scope for the generated corpus.
"""


class URLError(Exception):
    pass


SPECIAL = {"ftp": 21, "file": None, "http": 80, "https": 443, "ws": 80, "wss": 443}


def is_special(scheme):
    return scheme in SPECIAL


# --- percent-encode sets (defined over bytes 0..255) -----------------------

def _c0(b):
    return b <= 0x1F or b > 0x7E


_FRAG = {0x20, 0x22, 0x3C, 0x3E, 0x60}
_QUERY = {0x20, 0x22, 0x23, 0x3C, 0x3E}
_PATH_EXTRA = {0x3F, 0x60, 0x7B, 0x7D}
_USERINFO_EXTRA = {0x2F, 0x3A, 0x3B, 0x3D, 0x40, 0x5B, 0x5C, 0x5D, 0x5E, 0x7C}


def _in_fragment(b):
    return _c0(b) or b in _FRAG


def _in_query(b):
    return _c0(b) or b in _QUERY


def _in_special_query(b):
    return _in_query(b) or b == 0x27


def _in_path(b):
    return _in_query(b) or b in _PATH_EXTRA


def _in_userinfo(b):
    return _in_path(b) or b in _USERINFO_EXTRA


def pct_encode(s, in_set):
    out = []
    for ch in s:
        for b in ch.encode("utf-8"):
            if in_set(b):
                out.append("%%%02X" % b)
            else:
                out.append(chr(b))
    return "".join(out)


def pct_decode(s):
    """Percent-decode a string to bytes."""
    out = bytearray()
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "%" and i + 2 < n + 1 and i + 2 < n and _is_hex(s[i + 1]) and _is_hex(s[i + 2]):
            out.append(int(s[i + 1:i + 3], 16))
            i += 3
        else:
            out.extend(c.encode("utf-8"))
            i += 1
    return bytes(out)


def _is_hex(c):
    return c in "0123456789abcdefABCDEF"


def _is_ascii_digit(c):
    return "0" <= c <= "9"


def _is_ascii_alpha(c):
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _is_ascii_alnum(c):
    return _is_ascii_alpha(c) or _is_ascii_digit(c)


# --- host parsing ----------------------------------------------------------

FORBIDDEN_HOST = set("\x00\t\n\r #/:<>?@[\\]^|") | {"\x7f"}
FORBIDDEN_DOMAIN = FORBIDDEN_HOST | {chr(c) for c in range(0x00, 0x21)} | {"%", "\x7f"}


def parse_host(inp, special):
    if inp.startswith("["):
        if not inp.endswith("]"):
            raise URLError("unclosed IPv6")
        return "[" + _parse_ipv6(inp[1:-1]) + "]"
    if not special:
        return _parse_opaque_host(inp)
    domain = pct_decode(inp).decode("utf-8", "replace")
    ascii_domain = domain.lower()
    for ch in ascii_domain:
        if ch in FORBIDDEN_DOMAIN:
            raise URLError("forbidden domain code point")
    if _ends_in_number(ascii_domain):
        return _parse_ipv4(ascii_domain)
    return ascii_domain


def _parse_opaque_host(inp):
    for ch in inp:
        if ch in FORBIDDEN_HOST and ch != "%":
            raise URLError("forbidden host code point")
    return pct_encode(inp, _c0)


def _ends_in_number(host):
    parts = host.split(".")
    if parts and parts[-1] == "":
        if len(parts) == 1:
            return False
        parts = parts[:-1]
    if not parts:
        return False
    last = parts[-1]
    if last == "":
        return False
    if all(_is_ascii_digit(c) for c in last):
        return True
    # hex form
    v = last
    if v[:2] in ("0x", "0X"):
        v = v[2:]
        return all(_is_hex(c) for c in v) if v != "" else True
    return False


def _parse_ipv4_number(s):
    if s == "":
        raise URLError("empty ipv4 part")
    r = 10
    if len(s) >= 2 and s[:2] in ("0x", "0X"):
        s = s[2:]
        r = 16
    elif len(s) >= 2 and s[0] == "0":
        s = s[1:]
        r = 8
    if s == "":
        return 0
    digits = {8: "01234567", 10: "0123456789", 16: "0123456789abcdefABCDEF"}[r]
    for c in s:
        if c not in digits:
            raise URLError("invalid ipv4 number")
    return int(s, r)


def _parse_ipv4(host):
    parts = host.split(".")
    if parts[-1] == "":
        parts = parts[:-1]
    if len(parts) > 4:
        raise URLError("too many ipv4 parts")
    numbers = [_parse_ipv4_number(p) for p in parts]
    for n in numbers[:-1]:
        if n > 255:
            raise URLError("ipv4 part > 255")
    if numbers[-1] >= 256 ** (5 - len(numbers)):
        raise URLError("ipv4 last part too big")
    ipv4 = numbers[-1]
    for i, n in enumerate(numbers[:-1]):
        ipv4 += n * (256 ** (3 - i))
    a = (ipv4 >> 24) & 0xFF
    b = (ipv4 >> 16) & 0xFF
    c = (ipv4 >> 8) & 0xFF
    d = ipv4 & 0xFF
    return "%d.%d.%d.%d" % (a, b, c, d)


def _parse_ipv6(inp):
    address = [0] * 8
    piece_index = 0
    compress = None
    i = 0
    n = len(inp)
    if i < n and inp[i] == ":":
        if i + 1 >= n or inp[i + 1] != ":":
            raise URLError("ipv6 bad start")
        i += 2
        piece_index += 1
        compress = piece_index
    while i < n:
        if piece_index == 8:
            raise URLError("ipv6 too many pieces")
        if inp[i] == ":":
            if compress is not None:
                raise URLError("ipv6 multiple compress")
            i += 1
            piece_index += 1
            compress = piece_index
            continue
        value = 0
        length = 0
        while length < 4 and i < n and _is_hex(inp[i]):
            value = value * 0x10 + int(inp[i], 16)
            i += 1
            length += 1
        if i < n and inp[i] == ".":
            if length == 0:
                raise URLError("ipv6 bad ipv4-in-ipv6")
            i -= length
            if piece_index > 6:
                raise URLError("ipv6 no room for ipv4")
            numbers_seen = 0
            while i < n:
                ipv4_piece = None
                if numbers_seen > 0:
                    if inp[i] == "." and numbers_seen < 4:
                        i += 1
                    else:
                        raise URLError("ipv6 ipv4 bad dot")
                if i >= n or not _is_ascii_digit(inp[i]):
                    raise URLError("ipv6 ipv4 non-digit")
                while i < n and _is_ascii_digit(inp[i]):
                    number = int(inp[i])
                    if ipv4_piece is None:
                        ipv4_piece = number
                    elif ipv4_piece == 0:
                        raise URLError("ipv6 ipv4 leading zero")
                    else:
                        ipv4_piece = ipv4_piece * 10 + number
                    if ipv4_piece > 255:
                        raise URLError("ipv6 ipv4 > 255")
                    i += 1
                address[piece_index] = address[piece_index] * 0x100 + ipv4_piece
                numbers_seen += 1
                if numbers_seen == 2 or numbers_seen == 4:
                    piece_index += 1
            if numbers_seen != 4:
                raise URLError("ipv6 ipv4 incomplete")
            break
        elif i < n and inp[i] == ":":
            i += 1
            if i >= n:
                raise URLError("ipv6 colon at end")
        elif i < n:
            raise URLError("ipv6 unexpected char")
        address[piece_index] = value
        piece_index += 1
    if compress is not None:
        swaps = piece_index - compress
        piece_index = 7
        while piece_index != 0 and swaps > 0:
            address[piece_index], address[compress + swaps - 1] = \
                address[compress + swaps - 1], address[piece_index]
            piece_index -= 1
            swaps -= 1
    elif compress is None and piece_index != 8:
        raise URLError("ipv6 wrong piece count")
    return _serialize_ipv6(address)


def _serialize_ipv6(address):
    # Find longest run of zeros (length > 1) to compress.
    best_start = None
    best_len = 0
    cur_start = None
    cur_len = 0
    for i in range(8):
        if address[i] == 0:
            if cur_start is None:
                cur_start = i
                cur_len = 1
            else:
                cur_len += 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
        else:
            cur_start = None
            cur_len = 0
    compress = best_start if best_len > 1 else None
    out = []
    ignore0 = False
    for i in range(8):
        if ignore0:
            if address[i] == 0:
                continue
            ignore0 = False
        if compress == i:
            out.append("::" if i == 0 else ":")
            ignore0 = True
            continue
        out.append("%x" % address[i])
        if i != 7:
            out.append(":")
    return "".join(out)
