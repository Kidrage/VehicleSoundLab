"""Observed first-frame anchors and chirplet families for the fast startup flare."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from shift_evidence_v1.spectrum import observe
from state_colour_v2.clock import follow,peaks
from phase_clock_v1.chirplet import observe as chirplets
from phase_clock_v1.projection import polish,independent_agreement
from exterior_clock_v1.warp import warp
from startup_catch_v1.clock import diagnostics
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_explorer.py')
r=dict(result='running',source_sha256=sha(__file__),cases=[],physical_RPM_identified=False)
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    context=x[round((37.1-33)*48000):round((38.4-33)*48000)]
    for method in ('fft','chirplet'):
        print(method,flush=True)
        s=observe(context,37.1,80) if method=='fft' else chirplets(context,37.1)
        np.savez_compressed(a.out/(method+'.npz'),hz=s['hz'],seconds=s['seconds'],power=s['power_low'])
        for start,stop in ((37.3,38.1),(37.4,38.1),(37.5,38.1)):
            first=np.flatnonzero((s['seconds']>=start-1e-8)&(s['seconds']<=stop+1e-8))[0]
            f,power=peaks(s['hz'],s['power_low'][:,first])
            for reference in (2,3,4,5,6,8):
                anchors=f[(f/reference>=25)&(f/reference<=65)]/reference
                for anchor in anchors:
                    path=follow(s['hz'],s['seconds'],s['power_low'],start,stop,float(anchor),reference)
                    row=dict(method=method,seconds=[start,stop],reference=reference,anchor=float(anchor),status=path['status'])
                    if path['rows']:
                        times=np.array([v['seconds'] for v in path['rows']]);root=np.array([v['root_hz'] for v in path['rows']])
                        row.update(rows=path['rows'],root_range=[float(min(root)),float(max(root))])
                        try:
                            y,pos,info=warp(x,33,times,root,float(times[0]),float(times[-1]))
                            y,pos,phase=polish(x,33,y,pos,reference,info['source_cutoff_hz'])
                            measured=diagnostics(y,reference);agreement=independent_agreement(measured)
                            row.update(phase=phase,diagnostics=measured,agreement=agreement)
                            if agreement['passed']:
                                key=f'{method}_{start}_{reference}_{len(r["cases"])}.npz'
                                np.savez_compressed(a.out/key,normalized=y,positions=pos)
                                row.update(candidate=key,sha256=sha(a.out/key))
                        except ValueError as exc:row['phase_error']=str(exc)
                    r['cases'].append(row)
    r['result']='fast_paths_observed'
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
passing=[{k:v for k,v in row.items() if k in ('method','seconds','reference','anchor','root_range','agreement','candidate')} for row in r['cases'] if row.get('agreement',{}).get('passed')]
print(json.dumps(dict(result=r['result'],cases=len(r['cases']),connected=sum(bool(v.get('rows')) for v in r['cases']),passing=passing)))
