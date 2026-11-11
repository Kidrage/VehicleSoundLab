"""Compare FFT/chirplet observed families in the same eight approved A passages."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from phase_clock_v1.chirplet import observe
from state_colour_v2.clock import follow

args.out.mkdir(parents=True,exist_ok=False)
audio,source=read(args.workspace,'A_exterior_revs_extended','exterior_dynamic_observation')
old_path=args.workspace/'references/analysis/state_colour_v2/clocks_attempt2/report.json'
old=json.loads(old_path.read_text(encoding='utf-8'))
cases=[('rise1',232.25,232.60,26.4),('fall1',232.65,233.45,54),
       ('rise2',234.95,235.32,26.4),('fall2',235.40,236.40,52),
       ('rise3',237.90,238.14,35.2),('fall3',238.22,239.10,58),
       ('rise4',240.60,240.85,31),('fall4',240.97,241.66,53)]
report=dict(schema='vsl.chirplet-real-clocks/1',source=source,cases={},old_clocks_sha256=sha(old_path),
    interpretation='Observed chirplet peaks, same4dB/-30dB/16oct-s path rules; no missing-line interpolation or RPM claim')
fig,axes=plt.subplots(4,2,figsize=(12,12),layout='constrained')
for ax,(name,start,stop,anchor) in zip(axes.ravel(),cases):
    first=round((start-.1-source['seconds'][0])*48000);last=round((stop+.1-source['seconds'][0])*48000)
    at=source['seconds'][0]+first/48000
    s=observe(audio[first:last],at)
    np.savez_compressed(args.out/(name+'.npz'),**s)
    paths={str(ref):follow(s['hz'],s['seconds'],s['power_low'],start,stop,anchor,ref) for ref in (5,10)}
    report['cases'][name]=paths
    for ref,path in paths.items():
        if path['rows']:ax.plot([r['seconds'] for r in path['rows']],[r['root_hz'] for r in path['rows']],label='chirplet ref'+ref)
    rows=old['cases'][name]['5']['rows']
    if rows:ax.plot([r['seconds'] for r in rows],[r['root_hz'] for r in rows],':',label='FFT ref5')
    ax.set(title=name,xlabel='Source seconds',ylabel='Acoustic root Hz',xlim=(start,stop));ax.legend(fontsize=7)
    print(name,{k:v['status'] for k,v in paths.items()},flush=True)
fig.savefig(args.out/'families.png',dpi=130);plt.close(fig)
repo=Path(__file__).resolve().parents[1]
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in (Path(__file__),repo/'tools/phase_clock_v1/chirplet.py',repo/'tools/state_colour_v2/clock.py')}
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
