"""Known short bursts first, then fixed full-source D screening; no event label."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.scan import scan_file
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    for name in ('tools/probe_short_event_scan_v1.py','tools/event_authoring/scan.py','research/short_event_scan_v1_plan.json'):
        target=out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    report=dict(result='running',goal_complete=False,physical_identity_confirmed=False,timbre_accepted=False)
    try:
        rate=48000;t=np.arange(3*rate)/rate;carrier=.08*np.sin(2*np.pi*160*t)
        results=[]
        for seed in (1049,17467,28123,54123):
            rng=np.random.default_rng(seed)
            pulse=np.zeros(len(t));first=round((1.4-.002)*rate)
            pulse[first:first+192]=.3*rng.normal(size=192)*np.hanning(192)
            x=carrier+pulse
            path=out/f'burst-{seed}.wav';sf.write(path,np.column_stack([x,-x]),rate,subtype='FLOAT')
            old=scan_file(path);short=scan_file(path,mode='short_high')
            old_near=[r for r in old['candidates'] if abs(r['source_seconds']-1.4)<.06 and r['both_full_band_above_3db']]
            new_near=[r for r in short['candidates'] if abs(r['source_seconds']-1.4)<.02 and r['both_full_band_above_3db']]
            assert not old_near and len(new_near)==1,(seed,old_near,new_near)
            mono=out/f'mono-{seed}.wav';phase=out/f'inphase-{seed}.wav'
            sf.write(mono,x,rate,subtype='FLOAT');sf.write(phase,np.column_stack([x,x]),rate,subtype='FLOAT')
            assert scan_file(phase,mode='short_high')==short
            mono_rows=scan_file(mono,mode='short_high')['candidates']
            assert len(mono_rows)==len(short['candidates'])
            for left,right in zip(mono_rows,short['candidates']):
                for key in ('source_seconds','event_seconds','before_seconds','after_seconds','both_full_band_above_3db'):
                    assert left[key]==right[key]
                for key in ('before','after'):
                    assert abs(left['contrast_db'][key]-right['contrast_db'][key])<1e-12
            native,_=sf.read(path,dtype='float64',always_2d=True)
            for row in short['candidates']:
                powers={}
                for key in ('event','before','after'):
                    a,b=[round(v*rate) for v in row[key+'_seconds']]
                    powers[key]=float(np.mean(native[a:b]**2))
                    assert powers[key]==row['windows'][key]['mean_channel_power']
                for key in ('before','after'):
                    db=float(10*np.log10(max(powers['event'],1e-30)/max(powers[key],1e-30)))
                    assert abs(db-row['contrast_db'][key])<1e-12
            save(out/f'known-{seed}.json',short)
            results.append(dict(seed=seed,short_event=new_near[0],original100ms_qualification_misses=True))
        for name,x in [('steady',carrier),('silence',carrier*0),('gradual',carrier*(1+.3*t/3))]:
            path=out/(name+'.wav');sf.write(path,x,rate,subtype='FLOAT')
            actual=scan_file(path,mode='short_high')
            assert not any(r['both_full_band_above_3db'] for r in actual['candidates'])
        report['known']=dict(four_bursts=results,polarity_exact_mono_time_exact_contrast_1e12=True,all_powers_independently_exact=True,
            no_qualified_steady_silence_gradual=True)
        print('Known short bursts and negative controls passed',flush=True)
        legacy=[]
        for name,file in [('D',data/'references/analysis/D_event_context_v1/scan1/report.json'),
                          ('A',data/'references/analysis/A_exterior_event_v1/scan1/report.json'),
                          ('F3',data/'references/analysis/F3_event_context_v1/scan1/report.json')]:
            old=load(file);actual=scan_file(old['source'],old['requested_ranges'])
            expected=[{k:v for k,v in row.items() if k!='source_id'} for row in old['candidates']]
            assert actual['candidates']==expected and actual['blocks']==old['blocks']
            assert actual['detector']==old['detector']
            legacy.append(dict(source=name,candidates=len(expected),default_exact=True))
        report['legacy']=legacy
        print('Frozen high scans remain exact',flush=True)
        spec=load(repo/'references/segments_v1.json')['sources']['D']
        assert any(row['id']=='D' and row['approved'] for row in load(data/'references/approval_manifest.json'))
        source=data/spec['master'];assert sha(source)==spec['master_sha256']
        actual=scan_file(source,mode='short_high')
        actual.update(source=str(source),source_sha256=spec['master_sha256'],source_id='D')
        save(out/'D-short-scan.json',actual)
        qualified=[r for r in actual['candidates'] if r['both_full_band_above_3db']]
        report.update(result='passed',D=dict(candidates=len(actual['candidates']),qualified=qualified),
            scan_only=True,fit_performed=False,new_download=False)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result='passed',D_candidates=report['D']['candidates'],D_qualified=len(report['D']['qualified'])),flush=True)


if __name__=='__main__':main()
