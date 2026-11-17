"""Independent saved-audio audit of full spectral-budget source candidates."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from audit_startup_contour_ensemble_v1 import EDGES, powers
from research_archive_v1 import load, save, sha


def fixed(profile):
    value=deepcopy(profile)
    for group in value['modal'].get('contours',[]):group.pop('gain')
    for band in value['bands']:band.pop('gain')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/Path(__file__).name)
    shutil.copy2(Path(__file__).with_name('audit_startup_contour_ensemble_v1.py'),args.output/'independent_fft_helper.py')
    report=load(args.input/'report.json');assert report['result']=='passed'
    f=np.fft.rfftfreq(2048,1/48000);window=.5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
    weight=np.full(1025,2/(2048*(window@window)));weight[[0,-1]]*=.5
    def psd(wave):
        starts=np.arange(0,len(wave)-2048+1,1024)
        z=np.fft.rfft(wave[starts[:,None]+np.arange(2048)[None,:]]*window[None,:,None],axis=1)
        return (z.real**2+z.imag**2).mean(axis=(0,2))*weight
    def source(binding):
        assert sha(Path(binding['path']))==binding['sha256']
        with sf.SoundFile(binding['path']) as stream:
            stream.seek(binding['first_frame'])
            return stream.read(binding['last_frame']-binding['first_frame'],dtype='float64',always_2d=True)
    all_waves,rows,eligible,dbdiff,shapediff={},[],[],[],[]
    for c in report['cases']:
        folder=args.input/c['kind']
        candidate=load(folder/'candidate-before-validation.json')
        assert sha(folder/'candidate-before-validation.json')==c['candidate_sha256']
        assert fixed(candidate)==fixed(load(folder/'designed-profile.json'))
        original=deepcopy(load(folder/'original-event-profile.json')['parameters'])
        original['bands']=[];original.pop('noise_lowpass_hz',None)
        modal=deepcopy(candidate['modal'])
        for p in (original,modal):
            for group in p.get('contours',[]):group.pop('gain')
        assert original==modal
        x,bg=source(c['source']),source(c['background'])
        excess=np.maximum(psd(x)-psd(bg),0)
        targets=np.array([excess[(f>=lo)&(f<hi)].sum() for lo,hi in EDGES])
        timecurve=np.maximum(powers(x,240)[1:5]-powers(bg,240)[1:5].mean(axis=1)[:,None],0)
        reference=timecurve/timecurve.mean(axis=1)[:,None]
        significant=targets>=targets.sum()*1e-4
        checks=[]
        for seedrow in c['seeds']:
            data={}
            for label,key in [('old_C','old'),('candidate_Python','candidate')]:
                path=folder/(label+'-'+str(seedrow['seed'])+'.wav')
                wave,rate=sf.read(path,dtype='float64')
                assert rate==48000 and wave.ndim==1 and np.isfinite(wave).all()
                all_waves[str(path)]=sha(path)
                observation=wave[:len(x)]
                energy=powers(observation,1024).mean(axis=1)
                db=10*np.log10(np.maximum(energy,1e-30)/np.maximum(targets,1e-30))
                passed=np.where(significant,abs(db)<=3,energy<=np.maximum(2*targets,targets.sum()*2e-4))
                curve=powers(observation,240)[1:5]
                errors=np.sqrt(np.mean((curve/curve.mean(axis=1)[:,None]-reference)**2,axis=1))
                expected=np.array([b['error_db'] for b in seedrow[key]['bands']])
                np.testing.assert_allclose(db,expected,atol=1e-11,rtol=1e-12)
                np.testing.assert_allclose(errors,seedrow[key]['shape_rmse'],atol=1e-12,rtol=1e-12)
                dbdiff.append(float(np.max(abs(db-expected))))
                shapediff.append(float(np.max(abs(errors-seedrow[key]['shape_rmse']))))
                data[key]=dict(spectral_pass=bool(passed.all()),shape_rmse=errors.tolist())
            nonregression=bool(np.all(np.asarray(data['candidate']['shape_rmse'])<=
                                     np.asarray(data['old']['shape_rmse'])+1e-10))
            qualified=nonregression and data['candidate']['spectral_pass']
            assert qualified==seedrow['candidate']['qualified']
            checks.append(dict(seed=seedrow['seed'],split=seedrow['split'],**data,
                               temporal_nonregression=nonregression,qualified=qualified))
        before=np.array([r['old']['shape_rmse'] for r in checks if r['split']=='training'])
        after=np.array([r['candidate']['shape_rmse'] for r in checks if r['split']=='training'])
        old=np.mean((before/np.maximum(before,.05))**2);new=np.mean((after/np.maximum(before,.05))**2)
        improvement=float((old-new)/old)
        assert abs(improvement-c['relative_legacy_shape_improvement'])<1e-11
        accepted=bool(c['fitting']['phaseI']['feasible'] and improvement>1e-5 and all(r['qualified'] for r in checks))
        assert accepted==c['eligible_for_C_prototype'] and not c['adopted']
        if accepted:eligible.append(c['kind'])
        rows.append(dict(kind=c['kind'],checks=checks,eligible=accepted,weighted_training_shape_improvement=improvement))
    assert eligible==report['qualified_cases']==[]
    repo=Path(__file__).resolve().parents[1]
    runtime=load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime)==459 and len(all_waves)==32
    assert all(sha(repo/name)==digest for name,digest in runtime.items())
    save(args.output/'report.json',dict(result='passed',reviewed_report=str(args.input/'report.json'),
        reviewed_report_sha256=sha(args.input/'report.json'),cases=rows,waveforms=all_waves,qualified_cases=eligible,
        max_spectral_db_disagreement=max(dbdiff),max_shape_rmse_disagreement=max(shapediff),
        runtime_voice_files_unchanged=459,no_fit_render_or_selection_performed=True,
        goal_complete=False,timbre_accepted=False))
    print('32 saved audio files and all training/held-out gates independently checked; neither promoted',flush=True)


if __name__=='__main__':main()
