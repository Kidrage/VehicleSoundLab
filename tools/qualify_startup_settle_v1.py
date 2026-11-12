"""Apply the existing two-unfitted-carrier rule to all low orders, not only five probes."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
from drive_evidence_v1.sources import read,sha
from drive_evidence_v1.family import follow
from exterior_clock_v1.warp import warp
from phase_clock_v1.projection import polish,independent_agreement
from startup_catch_v1.clock import diagnostics

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_qualifier.py')
r=dict(result='running',source_sha256=sha(__file__),physical_RPM_identified=False)
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    hz,t,z=signal.stft(x,48000,nperseg=7680,noverlap=7440,axis=0,boundary=None,padded=False);t+=33
    path=follow(hz,t,np.mean(abs(z)**2,axis=1),38.35,39.65,35,reference_multiple=3,
        check_multiples=(2,4,5,6,7,8,10),max_octaves_per_second=8,root_bounds=(25,65))
    assert path['rows'];times=np.array([v['seconds'] for v in path['rows']]);root=np.array([v['root_hz'] for v in path['rows']])
    normalized,positions,info=warp(x,33,times,root,float(times[0]),float(times[-1]))
    polished,pos,qual=polish(x,33,normalized,positions,3,info['source_cutoff_hz'])
    values=diagnostics(polished,3);agreement=independent_agreement(values)
    r.update(path=path,warp=info,phase=qual,all_low_order_diagnostics=values,agreement=agreement)
    r['result']='qualified_local_settle' if agreement['passed'] else 'not_qualified'
    if agreement['passed']:
        np.savez_compressed(a.out/'settle.npz',normalized=polished,positions=pos)
        r['candidate_sha256']=sha(a.out/'settle.npz')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:r[k] for k in ['result','agreement','all_low_order_diagnostics']}))
