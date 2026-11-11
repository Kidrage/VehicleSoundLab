"""Capture a no-file-I/O renderer benchmark; timings are not realtime proof."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--plan', type=Path, required=True)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


plan = json.loads(args.plan.read_text(encoding='utf-8'))
args.out.mkdir(parents=True, exist_ok=False)
(args.out/'bin').mkdir()
probe = args.out/'bin/VslAtlasPerf_probe.exe'
shutil.copy2(args.probe, probe)
for name in ('VslAtlasMonitor.exe', 'VslAtlasTake_render.exe', 'VslAtlasDrive_probe.exe'):
    shutil.copy2(repo/'handoff-build/bin/Release'/name, args.out/'bin'/name)
shutil.copy2(args.plan, args.out/'plan.json')
paths = [Path(__file__), repo/'handoff/CMakeLists.txt']
for folder in ('src', 'modules', 'experiments/atlas_monitor_v1', 'experiments/atlas_perf_v1'):
    paths += [p for p in sorted((repo/folder).rglob('*')) if p.suffix in ('.c', '.h') or p.name == 'CMakeLists.txt']
for folder in ('exterior_anchors_v1', 'cabin_anchors_v1', 'residual_atlas_v1'):
    paths += [p for p in sorted((repo/'voices'/folder).iterdir()) if p.is_file()]
sources = {}
for path in paths:
    dest = args.out/'exact_sources'/path.relative_to(repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    sources[path.relative_to(repo).as_posix()] = sha(path)
metadata = dict(schema='vsl.atlas-performance/1', result='running',
    git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    probe_sha256=sha(probe), plan_sha256=sha(args.plan), source_sha256=sources,
    measurement='QPC wall time around processing only; output hashing/control/model loading outside timed sections. CPU cycles include QPC calls.',
    limits=['Normal-priority offline process; no device callback or hard-realtime qualification',
            'Isolated component controls differ from the full driving passage; costs are diagnostic, not additive',
            'Thread cycles exclude descheduling but are not elapsed seconds or invariant CPU-frequency measures'])
(args.out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
runs = []
try:
    for repeat in range(plan['repeats']):
        for case in plan['cases']:
            trace = args.out/(case['name']+'_'+str(repeat)+'.csv')
            command = [str(probe), *[str(case[k]) for k in ('bank', 'mode', 'block', 'channels', 'capture', 'propagation', 'seconds')], 'shifts', str(trace)]
            if 'flush' in case:
                command.append(str(case['flush']))
            started = time.time()
            completed = subprocess.run(command, cwd=repo, capture_output=True, check=True, timeout=180)
            row = json.loads(completed.stdout)
            row.update(case=case['name'], repeat=repeat, command=command, host_seconds=time.time()-started,
                       trace_sha256=sha(trace))
            runs.append(row)
            with (args.out/'runs.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n')
            print(json.dumps({k: row[k] for k in ('case', 'repeat', 'process_seconds', 'p99_block_ms', 'budget_exceedances')}), flush=True)
    metadata.update(result='pass', runs=runs)
except Exception as exc:
    metadata.update(result='failed', runs=runs, error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
