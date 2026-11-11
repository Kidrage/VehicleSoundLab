"""Re-observe A repeats with the two-cycle phase refiner and separate-carrier gate."""
import argparse
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
parser.add_argument('--method',choices=('short','debiased'),required=True)
parser.add_argument('--clocks',type=Path)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import read,sha
from state_dna_v1.compare import describe
from phase_clock_v1.projection import polish as short_polish
from phase_clock_v1.debiased import polish as debiased_polish
polish=short_polish if args.method=='short' else debiased_polish
from state_colour_v2.features import shape_delta,select_windows

args.out.mkdir(parents=True,exist_ok=False)
clock_path=(args.clocks/'report.json') if args.clocks else args.workspace/'references/analysis/state_colour_v2/clocks_attempt2/report.json'
clocks=json.loads(clock_path.read_text(encoding='utf-8'))
audio,source=read(args.workspace,'A_exterior_revs_extended','exterior_dynamic_observation')
assert source['catalog_sha256']==clocks['source']['catalog_sha256']
report=dict(schema='vsl.phase-clock-real-observation/1',method=args.method,source=source,clocks_sha256=sha(clock_path),
    cases={},pairs=[],excluded=[],bins=[],limits=['Acoustic root and rise/fall, not measured pedal/load/fuel/RPM',
        'Same video rear context; unknown microphone transfer and A/V relation',
        'Independent-carrier gate rejects clear disagreement but does not prove a physical engine clock'])
all_rows={}
for name,paths in clocks['cases'].items():
    path=paths['5']['rows']
    if not path:report['excluded'].append(dict(case=name,reason='No connected reference5 path; not repaired'));continue
    times=np.array([r['seconds'] for r in path]);roots=np.array([r['root_hz'] for r in path])
    try:
        y,where,e,z=describe(audio,source['seconds'][0],times,roots,times[0],times[-1],phase_refiner=polish)
    except ValueError as exc:report['excluded'].append(dict(case=name,reason=str(exc)));continue
    directory=args.out/name;directory.mkdir()
    sf.write(directory/'normalized.wav',y,48000,subtype='FLOAT')
    keep=select_windows(e,name.startswith('rise'));selected=np.flatnonzero(keep)
    disjoint=[]
    for k in selected:
        if not disjoint or k-disjoint[-1]>=16:disjoint.append(int(k))
    e.update(selected_windows=int(keep.sum()),selected_root_hz=np.array(e['window_root_hz'])[keep].tolist(),
        selected_nonoverlapping_window_count=len(disjoint))
    if keep.any():e['mean_power_LR']=np.mean(abs(z[keep])**2,axis=0).tolist()
    accepted=e['correction']['independent_agreement']['passed']
    e['eligible_for_diagnostic_comparison']=accepted
    if not accepted:report['excluded'].append(dict(case=name,reason='Fewer than2 supported separate L carriers agree'))
    report['cases'][name]=e;all_rows[name]=z
    np.savez_compressed(directory/'coordinates.npz',complex_rows=z,source_seconds=where,selected=keep)
    print(name,'separate carriers',e['correction']['independent_agreement']['orders'],'selected',len(selected),flush=True)
for pair in (1,2,4):
    a,b=(report['cases'].get(k+str(pair)) for k in ('fall','rise'))
    if not(a and b and a['selected_windows'] and b['selected_windows'] and
           a['eligible_for_diagnostic_comparison'] and b['eligible_for_diagnostic_comparison']):continue
    report['pairs'].append(dict(id=pair,rise_minus_fall_shape_db_LR=shape_delta(np.array(a['mean_power_LR']),np.array(b['mean_power_LR'])).tolist(),
        rise_root_mean=float(np.mean(b['selected_root_hz'])),fall_root_mean=float(np.mean(a['selected_root_hz'])),
        common_supported_hz=min(a['supported_hz_at_reference_root'],b['supported_hz_at_reference_root'])))

for lo,hi in ((30,35),(35,40),(40,45),(45,50),(50,55)):
    observation=dict(root_bin_hz=[lo,hi],cases={},paired_passages=[])
    for name,e in report['cases'].items():
        root=np.array(e['window_root_hz']);direction=np.gradient(root,np.array(e['window_source_seconds']))
        keep=(root>=lo)&(root<hi)&((direction>0) if name.startswith('rise') else (direction<0))
        selected=np.flatnonzero(keep);disjoint=[]
        for k in selected:
            if not disjoint or k-disjoint[-1]>=16:disjoint.append(int(k))
        if selected.size and e['eligible_for_diagnostic_comparison']:
            observation['cases'][name]=dict(windows=len(selected),nonoverlapping=len(disjoint),
                mean_root=float(np.mean(root[keep])),mean_power_LR=np.mean(abs(all_rows[name][keep])**2,axis=0).tolist())
    for pair in (1,2,4):
        if all(k+str(pair) in observation['cases'] for k in ('rise','fall')):observation['paired_passages'].append(pair)
    report['bins'].append(observation)
repo=Path(__file__).resolve().parents[1]
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in (Path(__file__),repo/'tools/phase_clock_v1/projection.py',repo/'tools/phase_clock_v1/debiased.py',repo/'tools/state_dna_v1/compare.py',repo/'tools/exterior_clock_v1/warp.py',repo/'tools/state_colour_v2/features.py',repo/'tools/sound_dna/windowed.py')}
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print('eligible pairs',len(report['pairs']),'bin replication',[(b['root_bin_hz'],b['paired_passages']) for b in report['bins']])
