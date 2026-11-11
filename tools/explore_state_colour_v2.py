"""Find independent rising/falling repeats in expanded approved A rear context."""
import argparse,json,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow
args.out.mkdir(parents=True,exist_ok=False)
x,source=read(args.workspace,'A_exterior_revs_extended','exterior_dynamic_observation')
s=observe(x,source['seconds'][0],80,hop=240)
np.savez_compressed(args.out/'observation.npz',**s)
cases=[('rise1',232.25,232.60,26.4),('fall1',232.65,233.45,54),
       ('rise2',234.95,235.32,26.4),('fall2',235.40,236.40,52),
       ('rise3',237.90,238.14,35.2),('fall3',238.22,239.10,58),
       ('rise4',240.60,240.85,31),('fall4',240.97,241.66,53)]
report=dict(source=source,cases={})
fig,ax=plt.subplots(2,1,figsize=(14,8),sharex=True,layout='constrained')
db=10*np.log10(s['power_low']+1e-30)
ax[0].pcolormesh(s['seconds'],s['hz'],db,vmin=db.max()-50,vmax=db.max(),cmap='magma',shading='auto',rasterized=True)
for name,start,stop,anchor in cases:
    paths={str(ref):follow(s['hz'],s['seconds'],s['power_low'],start,stop,anchor,ref) for ref in (5,10)}
    report['cases'][name]=paths
    for ref,selected in paths.items():
        if selected['rows']:ax[1].plot([r['seconds'] for r in selected['rows']],[r['root_hz'] for r in selected['rows']],label=name+' ref'+ref)
    print(name,{ref:dict(status=p['status'],range=[round(p['rows'][0]['root_hz'],2),round(p['rows'][-1]['root_hz'],2)] if p['rows'] else []) for ref,p in paths.items()},flush=True)
ax[0].set(ylim=(40,1000),ylabel='Observed Hz');ax[1].set(xlabel='Source seconds',ylabel='Acoustic root Hz',xlim=(231.8,242));ax[1].legend(ncol=4,fontsize=8)
fig.savefig(args.out/'clocks.png',dpi=140);plt.close(fig)
repo=Path(__file__).resolve().parents[1]
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in (Path(__file__),repo/'tools/state_colour_v2/clock.py')}
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
