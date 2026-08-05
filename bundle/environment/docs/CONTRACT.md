# Output contract

This file defines, exactly, what `urlp` must print. Grading is an exact
comparison of the component set, so read it closely.

## Invocation

```
python3 -m urlp <case-file>
```

The single positional argument is a path to a JSON file describing one case:

```json
{"input": "http://example.com/a/b", "base": "http://base/x"}
```

`input` is the string to parse. `base` is either a base URL string to resolve
against, or `null` for no base. Parse `input` against `base` exactly as
`new URL(input, base)` would (and `new URL(input)` when `base` is `null`).

On success: print one JSON object to stdout and exit `0`.
On any parse failure: exit non-zero. Anything on stderr is ignored.

## The object

```json
{"url": {
  "href": "http://example.com/a/b",
  "protocol": "http:",
  "username": "",
  "password": "",
  "host": "example.com",
  "hostname": "example.com",
  "port": "",
  "pathname": "/a/b",
  "search": "",
  "hash": ""
}}
```

A single key, `url`, holding the ten components below in this exact shape.
Nothing else in the object is read. Every value is a string.

| Field | Meaning (matches the URL API getters) |
|---|---|
| `href` | the full serialized URL |
| `protocol` | scheme followed by `:` (e.g. `http:`) |
| `username` | percent-encoded username, or `""` |
| `password` | percent-encoded password, or `""` |
| `host` | hostname, plus `:port` when a port is present |
| `hostname` | host without the port |
| `port` | port as a string, or `""` when absent or default |
| `pathname` | path (leading `/` for hierarchical URLs; the opaque string otherwise) |
| `search` | `""` if the query is null or empty, else `?` + query |
| `hash` | `""` if the fragment is null or empty, else `#` + fragment |

Note the asymmetry that trips people up: for `http://h/?`, `href` keeps the `?`
but `search` is `""`; likewise `#` for `hash`. The getters treat an empty
query/fragment like a null one, while the serialization keeps the delimiter.

## What the parser must do

Follow the WHATWG URL Standard's basic URL parser:

- **Schemes.** Special schemes are `http`, `https`, `ws`, `wss`, `ftp`, `file`;
  everything else is non-special. Special non-file URLs require a non-empty
  host. Non-special URLs may have an opaque path (e.g. `mailto:a@b.com`).
- **Default ports** are elided: `http://h:80/` has `port` `""`. Defaults are
  http/ws 80, https/wss 443, ftp 21, file none.
- **Host parsing.** Domains are lowercased. A host that is an IPv4 address (in
  any of the decimal/octal/hex forms the standard accepts, including fewer than
  four parts) is normalized to dotted-decimal. IPv6 literals in `[...]` are
  parsed and re-serialized in compressed form. Non-special schemes use opaque
  host parsing. Internationalized domain names (non-ASCII) do **not** appear in
  any case.
- **Path.** `.` and `..` segments are removed (`..` pops a segment); for special
  schemes `\` is treated like `/`. `file:` URLs handle Windows drive letters.
- **Percent-encoding.** Apply the correct percent-encode set per component
  (userinfo, path, query, special-query, fragment, C0 control). Existing valid
  `%XX` escapes are preserved; they are not decoded.
- **Relative resolution.** When a base is given and `input` is not absolute,
  resolve per the standard (relative/authority/path/query/fragment states).

## Errors

Inputs that the standard rejects (empty special host, port out of range, bad
IPv6, a relative reference with no base, and so on) expect a **non-zero exit and
no output**. If a supplied `base` does not itself parse as an absolute URL, the
whole case is a failure. Getting these right is worth as much as any other case.

Exit `0` with valid JSON, or exit non-zero. There is no third option.
