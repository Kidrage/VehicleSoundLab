"""Snapshot pinned Max/JS/preset text for route inspection; never fetch media."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.parse
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tree', type=Path, required=True)
parser.add_argument('--revision', required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--reuse', type=Path, help='Prior text snapshot; each reused file is checked against the pinned Git blob')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
tree_bytes = args.tree.read_bytes()
tree = json.loads(tree_bytes)
assert tree['sha'] == args.revision and not tree.get('truncated')
chosen = [r for r in tree['tree'] if r['type'] == 'blob' and (
    Path(r['path']).suffix in ('.maxpat', '.gendsp', '.js', '.maxproj') or
    r['path'].startswith('presets/') and r['path'].endswith('.json') or
    r['path'] in ('README.md', 'SOUND_DESIGN_GUIDE.md'))]
assert len({r['path'] for r in chosen}) == len(chosen)
(args.out/'tree.json').write_bytes(tree_bytes)
shutil.copy2(__file__, args.out/'executed_fetch.py')
head = subprocess.check_output(['git','ls-remote','https://github.com/Kidrage/VehicleSoundSynth.git','HEAD'],text=True).split()[0]
report = dict(schema='vsl.v6-route-text/1', result='running', revision=args.revision,
    remote_head_at_fetch=head, tree_sha256=hashlib.sha256(tree_bytes).hexdigest(),
    fetcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), plan=chosen,
    policy='Max/Gen/JS, preset JSON and two authored guides only; no audio/video/image download')
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def fetch(row):
    name = row['path']
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    url = 'https://raw.githubusercontent.com/Kidrage/VehicleSoundSynth/'+args.revision+'/'+urllib.parse.quote(name,safe='/~')
    last = None
    if args.reuse:
        source = args.reuse/'text'/name
        if source.is_file():
            data = source.read_bytes()
            assert len(data) == row['size']
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == row['sha']
            data.decode('utf-8-sig')
            target = args.out/'text'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            return dict(path=name,bytes=len(data),git_blob_sha1=row['sha'],sha256=hashlib.sha256(data).hexdigest(),reused=True)
    for attempt in range(2):
        try:
            request = urllib.request.Request(url,headers={'User-Agent':'VehicleSoundLab-research'})
            data = urllib.request.urlopen(request,timeout=20).read()
            assert len(data) == row['size'], name
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == row['sha'], name
            data.decode('utf-8-sig')
            target = args.out/'text'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
            return dict(path=name,bytes=len(data),git_blob_sha1=row['sha'],sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            last = exc
    raise RuntimeError(f'{name}: {last!r}')


try:
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(fetch,chosen))
    report.update(result='pass',files=records)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result='pass',revision=args.revision,files=len(records),bytes=sum(r['bytes'] for r in records))),flush=True)
