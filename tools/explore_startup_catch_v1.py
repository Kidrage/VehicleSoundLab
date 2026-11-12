"""Test observed low-rise line families and independent carrier phase agreement."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from drive_evidence_v1.sources import read,sha
from drive_evidence_v1.family import follow
from exterior_clock_v1.warp import warp
from phase_clock_v1.projection import polish
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_explorer.py')
r=dict(result='running',source_sha256=sha(__file__),paths=[],physical_RPM_identified=False)
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    for ms in (80,160):
        size=round(ms*.001*48000);hz,t,z=signal.stft(x,48000,nperseg=size,noverlap=size-240,axis=0,boundary=None,padded=False)
        power=np.mean(abs(z)**2,axis=1);t+=33
        for first,last,anchor in [(38.35,39.65,35),(37.40,38.00,50),(37.25,39.65,40)]:
            for reference in (2,3,5,8):
                checks=tuple(k for k in (2,3,4,5,6,7,8,10) if k!=reference)
                path=follow(hz,t,power,first,last,anchor,reference_multiple=reference,
                    check_multiples=checks,max_octaves_per_second=8,root_bounds=(25,65))
                row=dict(ms=ms,seconds=[first,last],anchor=anchor,reference=reference,status=path['status'])
                if path['rows']:
                    times=np.array([v['seconds'] for v in path['rows']]);root=np.array([v['root_hz'] for v in path['rows']])
                    row['root_range']=[float(min(root)),float(max(root))];row['rows']=path['rows']
                    try:
                        normalized,positions,info=warp(x,33,times,root,float(times[0]),float(times[-1]))
                        polished,pos,qual=polish(x,33,normalized,positions,reference,info['source_cutoff_hz'])
                        row['phase']=qual
                        if qual['independent_agreement']['passed']:
                            key=f'{ms}_{first}_{reference}';np.savez_compressed(a.out/(key+'.npz'),normalized=polished,positions=pos)
                            row['candidate_npz']=key+'.npz';row['sha256']=sha(a.out/row['candidate_npz'])
                    except ValueError as exc:row['phase_error']=str(exc)
                r['paths'].append(row)
    r['result']='observed_paths_only'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in r['paths']:
    print(json.dumps({k:v for k,v in row.items() if k not in ('rows','phase')}|dict(agreement=row.get('phase',{}).get('independent_agreement'),diagnostics=row.get('phase',{}).get('diagnostics'))))
