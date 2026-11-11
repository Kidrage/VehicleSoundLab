"""Cross-check multiple observed carrier families in A stationary exterior context."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
from drive_evidence_v1.family import follow

repository=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
frozen=json.loads((args.workspace/'baselines/drive_evidence_v1/manifest.json').read_text(encoding='utf-8'))
observation=args.workspace/'references/analysis/drive_evidence_v1/observed'
report=dict(schema='vsl.exterior-clock/1',cases={},limits=[
    'Relative acoustic coordinate only; no calibrated RPM/load/injector or bank identities',
    'Stationary rear view and moving close-tailpipe view must not be mixed as adjacent anchors',
    'Separate observed reference5 and reference10 paths may disagree; no interpolation across rejected spans'])
for case,anchor in [('A_exterior_blips',62),('A_exterior_low_rev',10.5)]:
    path=observation/case/'audio.npz'
    bound=next(row for row in frozen['external_payloads'] if row['path']==path.relative_to(args.workspace).as_posix())
    assert sha(path)==bound['sha256']
    with np.load(path) as data:
        hz=data['hz'];times=data['seconds'];power=data['psd_LR'].mean(axis=0)
    paths={}
    for reference in (5,10):
        for limit in (8,16,32):
            check=tuple(m for m in (2,3,5,7,10,15,20) if m!=reference)
            result=follow(hz,times,power,times[0],times[-1],anchor,reference,check,limit,(8,90))
            paths[f'reference{reference}_limit{limit}']=result
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
    keep=(hz>=35)&(hz<1500)
    db=10*np.log10(np.maximum(power[keep],1e-30))
    axes[0].pcolormesh(times,hz[keep],db,vmin=db.max()-50,vmax=db.max(),cmap='magma',shading='auto',rasterized=True)
    axes[0].set_ylabel('Observed Hz');axes[0].set_title(case+' | independent observed reference-line hypotheses')
    for name,path_result in paths.items():
        rows=path_result['rows']
        if not rows:continue
        axes[1].plot([r['seconds'] for r in rows],[r['root_hz'] for r in rows],lw=1,label=name,alpha=.8)
    axes[1].set_ylabel('Relative root Hz');axes[1].set_xlabel('Source seconds; no RPM assignment');axes[1].legend(ncol=3,fontsize=8)
    fig.savefig(args.out/(case+'.png'),dpi=140);plt.close(fig)
    report['cases'][case]=dict(observation_sha256=bound['sha256'],paths=paths,
        source_seconds=[float(times[0]),float(times[-1])])
    print(case,{name:value['status'] for name,value in paths.items()},flush=True)
report['source_sha256']={str(p.relative_to(repository)).replace('\\','/'):sha(p)
    for p in [Path(__file__),repository/'tools/drive_evidence_v1/family.py']}
(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
