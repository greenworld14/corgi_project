import json, glob, os, subprocess, sys
ref = os.path.abspath('bundle/solution/ref')
env = dict(os.environ); env['PYTHONPATH'] = ref
py = sys.executable
errs = []
for p in sorted(glob.glob('authoring/candidates/*/')):
    cid = os.path.basename(p.rstrip('/\\'))
    if not os.path.exists(os.path.join(p, 'main.c')):
        continue
    r = subprocess.run([py, '-m', 'pp', 'main.c', '-I.'], cwd=p,
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        errs.append((cid, r.stderr.strip()))
print('total erroring:', len(errs))
for cid, e in errs:
    src = open(os.path.join('authoring/candidates', cid, 'main.c'), encoding='utf-8').read().rstrip()
    print('===', cid, '===')
    print(src)
    print('  ERR:', e)
