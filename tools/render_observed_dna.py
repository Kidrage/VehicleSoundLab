"""Actual frozen native oscillators, independent complex-series check, fixed gain."""
import json
import subprocess
from runtime_review import ROOT,sha,rms
from phase_fingerprint import complex_coefficients
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/observed_dna_v1'
STUDY=ROOT/'references/analysis/phase_fingerprint_v1'
EXE=ROOT/'build-experiment-observed-dna/Release/observed_dna_probe.exe'
LABELS={'first_early':'第一次补油 · 前窗口','first_late':'第一次补油 · 后窗口','second_early':'第二次补油 · 前窗口'}


def independent_series(z,root,frames):
    # Direct complex exponential, independent of native sine/cosine recurrence,
    # coefficient slew and per-import loudness normalization.
    orders=np.arange(1,len(z)+1);y=np.empty((frames,2),float)
    for first in range(0,frames,4096):
        stop=min(frames,first+4096);t=np.arange(first,stop)/48000
        y[first:stop]=np.real(np.exp(2j*np.pi*root*t[:,None]*orders[None,:])@z)
    return y


def main():
    if (OUT/'results.json').exists() or (ROOT/'baselines/observed_dna_v1').exists():
        raise SystemExit('Preserve observed_dna_v1.')
    OUT.mkdir(parents=True,exist_ok=True)
    base=json.loads((STUDY/'results.json').read_text());cases={};page_data={};all_audio={}
    inputs={};files={}
    for name,snapshot in base['snapshots'].items():
        z=complex_coefficients(snapshot['fit']);root=snapshot['fit']['supplied_root_hz'];variants={}
        for method in ['fitted','common_flat']:
            entry=snapshot['files'][method];dna=[STUDY/entry[c]['file'] for c in ['L','R']]
            for path,c in zip(dna,['L','R']):
                assert sha(path)==entry[c]['sha256'];inputs[path.relative_to(ROOT).as_posix()]=sha(path)
            target=OUT/f'{name}_{method}.wav'
            command=[str(EXE),*map(str,dna),str(target)]
            result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=30)
            assert 'native 0.16.0' in result.stdout and '| pass' in result.stdout
            x,sr=sf.read(target,always_2d=True);assert sr==48000 and x.shape==(144000,2) and np.isfinite(x).all()
            expected_z=z if method=='fitted' else z*np.exp(-1j*np.angle(z[:,0])[:,None])
            expected=independent_series(expected_z,root,len(x))
            error=float(abs(x-expected).max());assert error<1e-7
            one=OUT/f'{name}_{method}_block1.wav'
            subprocess.run([str(EXE),*map(str,dna),str(one),'1'],check=True,capture_output=True,timeout=30)
            assert sha(one)==sha(target)
            fade=np.ones(len(x));fade[:240]=np.linspace(0,1,240);fade[-240:]=np.linspace(1,0,240)
            audition=x*.5*fade[:,None];assert abs(audition).max()<=.85
            path=OUT/f'audition_{name}_{method}.wav';sf.write(path,audition,sr,subtype='PCM_24')
            read,_=sf.read(path,always_2d=True);q=float(abs(read-audition).max());assert q<=2**-23+1e-12
            variants[method]=dict(raw=target.name,raw_sha256=sha(target),audition=path.name,audition_sha256=sha(path),
                gain_db=float(20*np.log10(.5)),endpoint_fade_ms=5,independent_series_max_error=error,
                block1_vs257_wav_sha256_equal=True,PCM24_max_error=q,raw_peak=float(abs(x).max()),raw_rms_dbfs=rms(x))
            all_audio[name,method]=x
            for path in [target,one,OUT/variants[method]['audition']]:files[path.name]=sha(path)
        cases[name]=dict(root_hz=root,source_window_seconds=snapshot['fit']['source_window_seconds'],
            weighted_local_fit_error_db_lr=snapshot['fit']['weighted_fit_error_db_lr'],variants=variants)
        page_data[name]=dict(label=LABELS[name],root_hz=root,source_window_seconds=cases[name]['source_window_seconds'],
            takes={key:'../renders/observed_dna_v1/'+v['audition'] for key,v in variants.items()},gain_db=variants['fitted']['gain_db'])
    fig,axes=plt.subplots(3,2,figsize=(11,8),constrained_layout=True)
    for row,(name,snapshot) in enumerate(base['snapshots'].items()):
        z=complex_coefficients(snapshot['fit']);root=snapshot['fit']['supplied_root_hz'];t=np.arange(2880)/48
        for method,label in [('fitted','Fitted phase'),('common_flat','Common phase rearranged')]:
            axes[row,0].plot(t,all_audio[name,method][:2880,0],lw=.8,label=label)
        axes[row,1].plot(root*np.arange(1,len(z)+1),20*np.log10(np.maximum(abs(z[:,0]),1e-20)),lw=1)
        axes[row,0].set(title=name+' / static C output, L',xlabel='Time / ms',ylabel='Amplitude')
        axes[row,1].set(title='Same harmonic magnitudes in both variants',xlabel='Frequency / Hz',ylabel='Observed L coefficient / dBFS',xlim=(0,8000))
        for ax in axes[row]:ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8);fig.savefig(OUT/'observed_dna.png',dpi=150);plt.close(fig)
    files['observed_dna.png']=sha(OUT/'observed_dna.png')
    template=ROOT/'tools/observed_dna_page.html';page=ROOT/'research/录音DNA相位试听V1.html'
    page.write_text(template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(page_data,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    for path in [STUDY/'results.json',ROOT/'references/analysis/phase_spaced_triplets_v1/results.json',
        ROOT/'references/analysis/rev_descent_v1/results.json']:
        inputs[path.relative_to(ROOT).as_posix()]=sha(path)
    reference=ROOT/'renders/exhaust_envelope_v1/reference_A_blips.wav';inputs[reference.relative_to(ROOT).as_posix()]=sha(reference)
    sources=[ROOT/'tools'/p for p in ['render_observed_dna.py','phase_fingerprint.py','analyze_phase_fingerprint.py','analyze_spaced_phase.py','observed_dna_page.html','seekable_review_player_v1.js']]
    sources+=list((ROOT/'experiments/observed_dna_v1').glob('*'))
    result=dict(schema='vsl.observed-dna/1',runtime='0.16.0 unchanged',seed=48271,cases=cases,page_data=page_data,
        files=files,inputs=inputs,sources={p.relative_to(ROOT).as_posix():sha(p) for p in sources if p.is_file()},
        binaries={p.relative_to(ROOT).as_posix():sha(p) for p in [EXE,ROOT/'build-v016/Release/vsl_core.lib']},
        page=dict(file=page.relative_to(ROOT).as_posix(),sha256=sha(page)),
        processing='Two native custom-DNA instances, one per observation channel. 250ms coefficient warmup, common phase zero, constant observed root at native 3000RPM. Native per-import normalization compensated to recover the fitted amplitudes and L/R level ratio. Float WAV is unclipped. All six auditions use the same fixed -6.0206dB and 5ms endpoint fades, no normalization, compression, denoising or highpass.',
        limits='Local mixed-recording harmonic snapshots frozen for 3 seconds, not engine-bank profiles or physical RPM. Phase rearrangement subtracts the L harmonic phase from both channels, preserving each magnitude and each harmonic L/R phase. No full driving reproduction, mechanical-source identification, noise deficit or perceptual realism conclusion.')
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',cases=3,auditions=6,maximum_analytic_C_error=max(v['independent_series_max_error'] for c in cases.values() for v in c['variants'].values()),
        audition_peak=max(abs(all_audio[k,m]*.5).max() for k,m in all_audio),page=str(page)),indent=2))


if __name__=='__main__':main()
