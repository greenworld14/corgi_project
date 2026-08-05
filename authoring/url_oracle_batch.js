// Batch Node oracle: read JSONL of {input, base} from stdin, write one result
// line per case in order: {"ok":true,"url":{...}} or {"ok":false}.
const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const out = [];
rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  let c;
  try { c = JSON.parse(line); } catch (e) { out.push(JSON.stringify({ ok: false })); return; }
  try {
    const u = (c.base !== null && c.base !== undefined) ? new URL(c.input, c.base) : new URL(c.input);
    out.push(JSON.stringify({ ok: true, url: {
      href: u.href, protocol: u.protocol, username: u.username, password: u.password,
      host: u.host, hostname: u.hostname, port: u.port, pathname: u.pathname,
      search: u.search, hash: u.hash,
    }}));
  } catch (e) {
    out.push(JSON.stringify({ ok: false }));
  }
});
rl.on('close', () => { process.stdout.write(out.join('\n') + '\n'); });
