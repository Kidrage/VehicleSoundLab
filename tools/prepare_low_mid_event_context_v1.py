"""Independently audit fixed low/mid scan powers and prepare qualified contexts."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/low_mid_event_scan_v1')
    plan=load(repo/'research/low_mid_event_scan_v1_plan.json');cases={};audits=[]
    for identity in ('D','E','A'):
        scan=load(root/(identity+'1')/'report.json')
        assert scan['requested_ranges']==plan['approved_material_ranges'][identity]
        assert scan['detector']['family']=='low_mid'
        assert sha(Path(scan['source']))==scan['source_sha256']
        errors=[]
        with sf.SoundFile(scan['source']) as stream:
            for row in scan['candidates']:
                at=row['source_seconds'];power={}
                for name,offset in [('event',(-.025,.075)),('before',(-.35,-.15)),('after',(.16,.36))]:
                    first,last=[round((at+d)*48000) for d in offset]
                    assert [round(v*48000) for v in row[name+'_seconds']]==[first,last]
                    stream.seek(first);x=stream.read(last-first,always_2d=True,dtype='float64')
                    assert np.isfinite(x).all() and len(x)==last-first
                    power[name]=sum(float(np.dot(x[:,c],x[:,c])) for c in range(2))/(2*len(x))
                contrast={name:10*np.log10(power['event']/power[name]) for name in ('before','after')}
                errors.append(max(abs(contrast[k]-row['contrast_db'][k]) for k in contrast))
                assert errors[-1]<1e-10
                assert row['both_full_band_above_3db']==(min(contrast.values())>=3)
                if row['both_full_band_above_3db']:
                    cases[identity+'_'+str(round(at*1000))]=dict(source=identity,
                        seconds=[at-1,at+1.5],frames=[at+d for d in (-.6,-.3,-.15,0,.15,.3,.6)],
                        crop=[0,0,1,1],caption='Complementary low/mid transient: inspect action and changing continuous engine before fitting')
        audits.append(dict(source=identity,candidates=len(errors),qualified=scan.get('candidates') and sum(r['both_full_band_above_3db'] for r in scan['candidates']) or 0,
            maximum_independent_contrast_error_db=max(errors,default=0),scan_sha256=sha(root/(identity+'1')/'report.json')))
    save(out/'contexts.spec.json',cases)
    save(out/'report.json',dict(result='passed',sources=audits,qualified_contexts=len(cases),
        fitting_performed=False,physical_identity_confirmed=False,goal_complete=False))
    shutil.copy2(__file__,out/'executed_prepare.py');print(audits,flush=True)


if __name__=='__main__':main()
