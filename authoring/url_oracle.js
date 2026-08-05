// Node oracle for the URL-parser freeze. Reads a case JSON {input, base} and
// prints the parsed component set, or exits 1 if `new URL()` throws.
// Usage: node url_oracle.js <case.json>
const fs = require('fs');
const c = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
try {
  const u = (c.base !== null && c.base !== undefined) ? new URL(c.input, c.base)
                                                       : new URL(c.input);
  const out = {
    url: {
      href: u.href, protocol: u.protocol, username: u.username,
      password: u.password, host: u.host, hostname: u.hostname,
      port: u.port, pathname: u.pathname, search: u.search, hash: u.hash,
    },
  };
  process.stdout.write(JSON.stringify(out));
} catch (e) {
  process.exit(1);
}
