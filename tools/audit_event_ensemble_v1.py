"""Independent FFT, saved actual-C waveform and fixed-window material audit."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from event_authoring.model import synth
from research_archive_v1 import load,save,sha

EDGES=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))


def psd(x):
    x=np.asarray(x)
    if x.ndim==1:x=x[:,None]
    n=min(2048,len(x));step=n-n//2;window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    blocks=np.array([np.fft.rfft(x[first:first+n]*window[:,None],axis=0)
                     for first in range(0,len(x)-n+1,step)])
    power=abs(blocks)**2/(48000*float(window@window))
    power[:,1:-1 if n%2==0 else None]*=2
    return np.fft.rfftfreq(n,1/48000),power.mean(axis=(0,2))


def powers(x):
    f,p=psd(x);return np.array([p[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]) for lo,hi in EDGES])


def crop(source,first,last):
    with sf.SoundFile(source) as stream:
        assert stream.samplerate==48000;stream.seek(first);return stream.read(last-first,dtype='float64',always_2d=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis/event_ensemble_v1');repo=Path(__file__).resolve().parents[1]
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    shutil.copy2(__file__,args.output/'executed_audit.py')
    try:
        review=load(args.review/'report.json');assert review['result']=='passed'
        rows=[];maximum=0.;differences=[]
        for case in review['cases']:
            name=case['name'];origin=case['source'];background=case['background']
            assert sha(origin['path'])==origin['sha256'] and sha(background['path'])==background['sha256']
            original=crop(origin['path'],origin['first_frame'],origin['last_frame'])
            bg=crop(background['path'],background['first_frame'],background['last_frame'])
            f,p=psd(original);fb,bp=psd(bg);excess=np.maximum(0,p-np.interp(f,fb,bp))
            targets=np.array([excess[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]) for lo,hi in EDGES]);total=float(targets.sum())
            published,_=sf.read(args.review/'review'/(name+'-reference.wav'),always_2d=True,dtype='float32')
            assert np.array_equal(published,(original*.25).astype('float32'))
            group=[];duration=len(original)/48000
            for variant in ('single','ensemble'):
                profile=load(args.review/(name+'-'+variant+'-profile.json'))
                if variant=='ensemble':assert profile==load(root/'probe1'/name/'profile.json')
                sequence,_=sf.read(args.review/'review'/(name+'-'+variant+'.wav'),dtype='float32')
                step=round((max(.2,duration+.15)+.15)*48000);rebuilt=np.zeros(step*8,dtype='float32')
                qualified=[]
                for index,trial in enumerate(case[variant]):
                    raw,_=sf.read(args.review/name/(variant+'-'+str(trial['seed'])+'.wav'),dtype='float32')
                    expected=synth(profile,seed=trial['seed'],seconds=len(raw)/48000,
                        release_at=duration if profile['gated'] else None)
                    expected=np.pad(expected,(0,len(raw)-len(expected)))
                    error=float(np.max(abs(raw-expected)));assert error<2e-6;maximum=max(maximum,error)
                    measured=powers(raw[:len(original)]);passed=[]
                    for target,power,band in zip(targets,measured,trial['bands']):
                        assert np.isclose(target,band['target_power'],rtol=2e-11,atol=1e-20)
                        assert np.isclose(power,band['generated_power'],rtol=2e-11,atol=1e-20)
                        db=float(10*np.log10(max(power,1e-30)/max(target,1e-30)))
                        differences.append(abs(db-band['error_db']));assert abs(db-band['error_db'])<2e-8
                        good=abs(db)<=3 if target>=total*1e-4 else power<=max(2*target,2e-4*total)
                        assert good==band['passed'];passed.append(good)
                    assert all(passed)==trial['qualified'];qualified.append(all(passed))
                    rebuilt[index*step:index*step+len(raw)]=raw*.25
                assert np.array_equal(sequence,rebuilt)
                group.append(dict(variant=variant,qualified=sum(qualified),trials=len(qualified)))
            rows.append(dict(name=name,original_PCM_exact=True,C_reference_exact=True,shared_gain_sequence_exact=True,variants=group))
        # Independent time-domain mean-square audit of the prior fixed200ms exploration.
        long=load(root/'B-long1/report.json');long_rows=[]
        for row in long['cases']:
            details=load(root/'B-long1'/('rank'+str(row['rank']))/'report.json')
            source=details['source'];event=crop(source['path'],source['first_frame'],source['last_frame'])
            ep=float(np.mean(event*event));values=[]
            for bgrow in details['backgrounds']:
                s=bgrow['source'];wave=crop(s['path'],s['first_frame'],s['last_frame'])
                value=float(10*np.log10(ep/np.mean(wave*wave)))
                assert abs(value-bgrow['full_contrast_db'])<1e-12;values.append(value)
            assert not all(v>=3 for v in values);long_rows.append(dict(rank=row['rank'],contrasts_db=values))
        # Only the off-line authoring/tooling changes; compare complete runtime inventory.
        current={p.relative_to(repo).as_posix():sha(p) for folder in ('src','modules','voices')
                 for p in (repo/folder).rglob('*') if p.is_file() and (p.suffix in ('.c','.h') or folder=='voices')}
        assert current==load(Path('E:/VehicleSoundLab/references/analysis/short_event_scan_v1/runtime.json')) and len(current)==459
        report.update(result='passed',cases=rows,all_48_C_waveforms_checked=True,
            independent_fft_max_db_difference=max(differences),C_python_max_error=maximum,
            six_fixed_long_windows=long_rows,runtime_unchanged=459,
            physical_afterfire_confirmed=False,no_new_audio_acceptance=True)
    except Exception as error:report.update(result='failed',error=repr(error));raise
    finally:save(args.output/'report.json',report)
    print(report,flush=True)


if __name__=='__main__':main()
