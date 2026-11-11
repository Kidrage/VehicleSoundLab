"""Compare independently observed clocks around A's stationary rev passages."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.family import follow
from drive_evidence_v1.sources import sha

args.out.mkdir(parents=True, exist_ok=False)
observation = args.workspace/'references/analysis/drive_evidence_v1/observed/A_exterior_blips/audio.npz'
manifest = json.loads((args.workspace/'baselines/drive_evidence_v1/manifest.json').read_text(encoding='utf-8'))
bound = next(r for r in manifest['external_payloads'] if r['path'] == observation.relative_to(args.workspace).as_posix())
assert sha(observation) == bound['sha256']
with np.load(observation) as data:
    hz, times, power = data['hz'], data['seconds'], data['psd_LR'].mean(axis=0)
cases = [('fall1', 238.1, 239.35, 64), ('rise1', 239.88, 240.04, 16.6),
         ('rise2', 240.60, 240.85, 30.8), ('fall2', 240.9, 241.75, 55)]
report = dict(schema='vsl.state-dna-clock-exploration/1', observation_sha256=sha(observation), cases={})
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, layout='constrained')
keep = (hz >= 35) & (hz < 1800)
db = 10*np.log10(np.maximum(power[keep], 1e-30))
axes[0].pcolormesh(times, hz[keep], db, vmin=db.max()-55, vmax=db.max(), shading='auto', rasterized=True, cmap='magma')
axes[0].set_ylabel('Observed Hz')
for name, start, stop, anchor in cases:
    paths = {}
    for reference in (5, 10):
        checks = tuple(m for m in (2, 3, 5, 7, 10, 15, 20) if m != reference)
        selected = follow(hz, times, power, start, stop, anchor, reference, checks, 16, (8, 90))
        paths[str(reference)] = selected
        rows = selected['rows']
        if rows:
            axes[1].plot([r['seconds'] for r in rows], [r['root_hz'] for r in rows], label=name+' ref'+str(reference))
    report['cases'][name] = paths
    print(name, {key: dict(status=value['status'], root=[round(r['root_hz'], 2) for r in value['rows'][::10]]) for key, value in paths.items()}, flush=True)
axes[1].set(xlabel='Source seconds; acoustic direction, not measured load/pedal', ylabel='Acoustic root Hz', xlim=(238, 242))
axes[1].legend(ncol=2, fontsize=8)
fig.savefig(args.out/'clocks.png', dpi=140)
plt.close(fig)
(args.out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
