"""Independent overlap-FFT stereo metrics and exact common-gain review checks."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','review','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',wave_checks=0,max_complex_coherence_error=0.,known_controls=0)
    try:
        review=load(a.review/'report.json');assert review['result']=='relative_phase_one_player_review_ready'
        for n,h in review['sources'].items():assert sha(repo/n)==sha(a.review/'exact_sources'/n)==h
        for n,h in review['inputs'].items():assert sha(n)==h
        def stereo(x):
            size=2048;window=np.hanning(size+1)[:-1]
            segments=np.lib.stride_tricks.sliding_window_view(x,size,axis=0)[::1024]
            segments=segments-segments.mean(axis=-1,keepdims=True)
            X=np.fft.rfft(segments*window,axis=-1)
            left=(abs(X[:,0])**2).mean(axis=0);right=(abs(X[:,1])**2).mean(axis=0)
            cross=np.mean(X[:,0]*X[:,1].conj(),axis=0)
            f=np.arange(size//2+1)*48000/size;values=[]
            for lo,hi in [[3000,6000],[6000,8000],[8000,10000],[10000,14000]]:
                mask=(f>=lo)&(f<hi);values.append(cross[mask].sum()/np.sqrt(left[mask].sum()*right[mask].sum()))
            return np.array(values)
        # Known phase and gain set the cross-spectrum convention explicitly.
        t=np.arange(16384)/48000
        frequencies=[4500,7000,9000,12000]
        left=sum(np.cos(2*np.pi*f*t) for f in frequencies)
        for gain,phase in [(1.,0.),(.37,.6)]:
            right=gain*sum(np.cos(2*np.pi*f*t-phase) for f in frequencies)
            actual=stereo(np.column_stack([left,right]))
            assert abs(actual-np.exp(1j*phase)).max()<2e-8
            report['known_controls']+=1
        table={bank['key']:bank for bank in review['banks']};waves={}
        audio=load(a.workspace/'references/analysis/relative_phase_v1/audio1/report.json')
        for clip in review['clips']:
            label=audio['cases'][int(clip['bank_key'][-1])-1]['label']
            if clip['variant']=='reference':
                source=a.review/(clip['bank_key']+'_native_unscaled.wav')
            elif clip['variant']=='original':
                source=a.workspace/f'baselines/radial_copula_v1/evidence/real2/{label}/original_{clip["seed"]}.wav'
            else:
                source=a.workspace/f'references/analysis/relative_phase_v1/audio1/{label}/{clip["variant"]}_{clip["seed"]}.wav'
            assert sha(source)==review['inputs'][str(source)]
            original,sr=sf.read(source,always_2d=True);output,rate=sf.read(a.review/clip['file'],always_2d=True)
            fade=.5-.5*np.cos(np.pi*np.arange(240)/240)
            expected=original*.5;expected[:240]*=fade[:,None];expected[-240:]*=fade[::-1,None]
            assert sr==rate==48000 and np.array_equal(output,expected.astype('float32').astype(float))
            assert sha(a.review/clip['file'])==clip['sha256'] and abs(output).max()<.95
            waves[(clip['bank_key'],clip['variant'],clip['seed'])]=stereo(original)
            report['wave_checks']+=1
        errors={k:[] for k in ('original','fixed_phase','relative_phase')}
        for i,row in enumerate(review['wave_statistics'],1):
            bank=f'bank{i}';source=waves[(bank,'reference',0)]
            def check(value,encoded):
                nonlocal report
                encoded=np.asarray(encoded);target=encoded[...,0]+1j*encoded[...,1]
                error=float(abs(value-target).max());assert error<2e-12
                report['max_complex_coherence_error']=max(report['max_complex_coherence_error'],error)
            check(source,row['source'])
            for variant in ('original','fixed_phase','relative_phase'):
                values=[waves[(bank,variant,seed)] for seed in (1,23117,61927)]
                for value,encoded in zip(values,row['variants'][variant]):check(value,encoded)
                error=np.mean([abs(value-source) for value in values],axis=0)
                assert abs(error-row['error_mean'][variant]).max()<2e-12
                errors[variant].extend(error)
        report.update(result='relative_phase_review_wave_metrics_verified',producer_sha256=sha(a.review/'report.json'),
            auditor_sha256=sha(a.out/'executed_audit.py'),
            mean_actual_wave_error={k:float(np.mean(v)) for k,v in errors.items()},
            relative_improves_vs_paired_fixed=int(np.sum(np.array(errors['relative_phase'])<errors['fixed_phase'])),
            coordinates=8,not_matched_replay=True,heard=False)
        save(a.out/'report.json',report);print(report['result'])
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
