"""Direct-FFT and clock-sensitivity checks for the independent shift passage."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--analysis',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe,region_stats,BANDS
args.out.mkdir(parents=True,exist_ok=False)
report=json.loads((args.analysis/'report.json').read_text(encoding='utf-8'))
for name,digest in report['source_sha256'].items():
    assert sha(args.analysis/'exact_sources'/name)==digest,name
    assert sha(repo/name)==digest,name
audio,provenance=read(args.workspace,'E_corsa_first_context','cabin_dynamic_observation')
assert provenance==report['provenance']
for case in report['known_controls']:
    assert max(r['max_error_db'] for r in case['rows'])<.05

# Recompute selected frames directly, using an independent Hann expression.
errors=[]
for ms in (40,60,80):
    data=np.load(args.analysis/f'window_{ms}.npz');size=round(ms*48)
    window=.5-.5*np.cos(2*np.pi*np.arange(size)/size);fft=16384
    hz=np.fft.rfftfreq(fft,1/48000)
    for i in (20,400,800,1200):
        first=round((data['seconds'][i]-47)*48000-size/2)
        z=np.fft.rfft(audio[first:first+size]*window[:,None],fft,axis=0)
        p=abs(z)**2/(fft*np.sum(window**2));p[1:-1]*=2
        direct=np.array([p[(hz>=lo)&(hz<hi)].sum(axis=0) for lo,hi in BANDS]).T
        saved=data['power'][:,:,i]
        error=float(abs(direct-saved).max());errors.append(error)
        assert np.allclose(direct,saved,rtol=1e-12,atol=1e-18)

exploration=json.loads((args.workspace/'references/analysis/shift_repeat_v1/exploration1/report.json').read_text(encoding='utf-8'))
family=next(f for f in exploration['families'] if f['start']==48 and f['anchor_root']==45)
ft=np.array([r['seconds'] for r in family['rows']]);ff=np.array([r['reference_hz'] for r in family['rows']])
sensitivity=[]
for event in report['analyses'][0]['events']:
    at=event['marker_seconds'];rows=[]
    for before in (-.02,0,.02):
        for after in (-.02,0,.02):
            x=np.clip((ft-at+.05)/.10,0,1)
            perturbed=ff*(1+before+(after-before)*x)
            obs=observe(audio,47,80,clock=(ft,perturbed))
            obs['power_LR']=obs['relative_power_LR'];obs['cross_LR']=obs['relative_cross_LR']
            pre=np.array(region_stats(obs,at-.20,at-.10)['power_LR']).mean(axis=0)
            post=np.array(region_stats(obs,at+.10,at+.20)['power_LR']).mean(axis=0)
            db=10*np.log10(post/pre);shape=db[3:5]-db[2]
            rows.append(dict(before_clock_fraction=before,after_clock_fraction=after,shape_db=shape.tolist()))
    values=np.array([r['shape_db'] for r in rows])
    sensitivity.append(dict(marker=at,rows=rows,minimum_db=values.min(axis=0).tolist(),maximum_db=values.max(axis=0).tolist()))

current=report['analyses'][0]['events']
short_window=[]
for i,event in enumerate(current):
    values=[]
    for analysis in report['analyses']:
        db=np.array(analysis['events'][i]['relative']['power_change_db'])
        values.append((db[3:5]-db[2]).tolist())
    short_window.append(dict(marker=event['marker_seconds'],shape_db_by_80_60_40ms=values,
                             spread_db=np.ptp(values,axis=0).tolist()))

index=repo/'handoff/C文件索引.csv'
with index.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
assert len(rows)==421
for row in rows:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']

result=dict(schema='vsl.shift-repeat-verification/1',result='pass',analysis_sha256=sha(args.analysis/'report.json'),
    direct_fft_max_absolute_error=max(errors),known_control_max_db=max(r['max_error_db'] for c in report['known_controls'] for r in c['rows']),
    clock_sensitivity=sensitivity,window_sensitivity=short_window,
    c_index_rows=len(rows),c_index_sha256=sha(index),runtime_changed=False,
    common_shift_profile_promoted=False,
    limits=['Sensitivity grid is engineering perturbation, not measured clock uncertainty',
            'Windows share one clock; low waveform correlation is not proof of independent ECU trials',
            'Observed passage differences are confounded with launch/gear/speed/acoustic path',
            'No fitted physical state/torque transfer or new timbre acceptance'])
source=[Path(__file__),repo/'tools/shift_evidence_v1/spectrum.py',repo/'tools/drive_evidence_v1/sources.py']
result['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in source}
for p in source:
    target=args.out/'exact_sources'/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
(args.out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result='pass',fft_error=max(errors),clock_ranges=[r['minimum_db']+r['maximum_db'] for r in sensitivity],
    window_spreads=[r['spread_db'] for r in short_window]),ensure_ascii=False))
