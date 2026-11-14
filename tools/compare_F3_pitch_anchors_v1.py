"""Render all five at one root, verify sparse C and describe stereo spectra."""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load,save,sha
p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','fit','out'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from idle_texture_v1.profile import load as model_load
from local_voice_batch_v1.audit_kernels import seeded_samples
from local_voice_batch_v1.bandlimited_controls import float_error

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},cases=[])


def spectrum(audio,plan):
    p=plan['measurement'];kw=dict(fs=48000,window='hann',nperseg=p['window_samples'],
        noverlap=p['overlap_samples'],nfft=p['fft_samples'],detrend=False,scaling='density')
    f,power=signal.welch(audio,axis=0,**kw)
    _,cross=signal.csd(audio[:,1],audio[:,0],**kw) # conjugate R times L
    rows=[]
    for lo,hi in p['bands_hz']:
        keep=(f>=lo)&(f<hi);pp=power[keep].sum(axis=0)*48000/p['fft_samples']
        cc=cross[keep].sum()*48000/p['fft_samples'];co=cc/np.sqrt(max(pp[0]*pp[1],1e-60))
        rows.append(dict(hz=[lo,hi],power_LR=pp.tolist(),signed_correlation=[float(co.real),float(co.imag)]))
    return dict(frames=len(audio),bands=rows)


try:
    names=['tools/compare_F3_pitch_anchors_v1.py','research/F3_pitch_compare_v1_plan.json',
        'tools/local_voice_batch_v1/audit_kernels.py','tools/local_voice_batch_v1/bandlimited_controls.py',
        'tools/idle_texture_v1/profile.py','tools/sustain_osc_v1/oracle.py','tools/research_archive_v1.py']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(repo/'research/F3_pitch_compare_v1_plan.json');fit=load(a.fit/'report.json')
    assert fit['qualified']==5 and fit['excluded']==0
    probe=repo/'build-bandlimited-dna-v1/bin/Release/sound_dna_bandlimited_export.exe'
    r['inputs'][str(probe)]=sha(probe)
    indices=[0,1,239,240,255,256,511,512,4800,11999,47999,95999,191999,383999]
    for row in fit['cases']:
        case=row['case'];source=a.fit/case['name'];folder=a.out/case['name'];folder.mkdir(exist_ok=False)
        model,root=model_load(source/'voice.model');r['inputs'][str(source/'voice.model')]=sha(source/'voice.model')
        normalized,rate=sf.read(source/'normalized.wav',always_2d=True);assert rate==48000
        ratio=Fraction(46.875/plan['common_root_hz']).limit_denominator(10000)
        ref=signal.resample_poly(normalized,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
        sf.write(folder/'reference64.wav',ref,48000,subtype='FLOAT')
        reference=spectrum(ref,plan);renders=[]
        for seed in plan['seeds']:
            dest=folder/('DNA64_%d.wav'%seed)
            argv=list(map(str,[probe,source/'voice.model',dest,8,64,1,seed,512]))
            done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=180)
            (folder/('C_%d.log'%seed)).write_bytes(done.stdout+done.stderr);assert done.returncode==0
            wave,rate=sf.read(dest,always_2d=True);assert wave.shape==(384000,2) and rate==48000 and np.isfinite(wave).all()
            expected=seeded_samples(model,64,seed,indices,bandlimited=True)
            error=float_error(wave[indices],expected)
            renders.append(dict(seed=seed,argv=argv,sha256=sha(dest),oracle=error,spectrum=spectrum(wave,plan)))
        r['cases'].append(dict(name=case['name'],native_root_hz=root,reference=reference,renders=renders))
        save(a.out/'report.json',r);print('PASS common64 C/oracle/stereo',case['name'],flush=True)
    # Descriptive unequal-duration training-reference versus generated spectra.
    means=[];differences=[];correlations=[];coh=[]
    for row in r['cases']:
        pp=np.mean([[b['power_LR'] for b in z['spectrum']['bands']] for z in row['renders']],axis=0)
        rr=np.array([b['power_LR'] for b in row['reference']['bands']])
        differences.append((10*np.log10(pp/rr)).mean(axis=1).tolist())
        means.append(10*np.log10(pp.mean(axis=1)))
        cr=np.mean([[complex(*b['signed_correlation']) for b in z['spectrum']['bands']] for z in row['renders']],axis=0)
        ref=np.array([complex(*b['signed_correlation']) for b in row['reference']['bands']])
        correlations.append(abs(cr-ref).tolist())
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    labels=['5th first early','5th first late','5th second early','5th second late','6th early']
    roots=[v['native_root_hz'] for v in r['cases']]
    axes[0,0].barh(labels,roots);axes[0,0].set(xlabel='Observed acoustic root Hz (not RPM)',xlim=(0,75))
    for j,x in enumerate(roots):axes[0,0].text(x+.4,j,'%.2f'%x,va='center',fontsize=9)
    fitrows=fit['cases']
    for j,row in enumerate(fitrows):
        values=[v for x in row['extraction']['heldout_coherence'].values() for v in x]
        axes[0,1].plot([j]*4,values,'o',alpha=.7)
    axes[0,1].axhline(.8,color='red',ls=':');axes[0,1].set(ylim=(.75,1.01),xticks=range(5),xticklabels=range(1,6),xlabel='Fixed observation',ylabel='Held-out3/7 L/R coherence')
    bandlabels=['28-120','120-400','400-1.2k','1.2-3k','3-6k','6-8k','8-10k','10-14k']
    for ax,values,title,vmin,vmax,cmap in [(axes[1,0],differences,'C minus short training reference / dB',-8,4,'coolwarm'),
                                        (axes[1,1],correlations,'Complex L/R correlation difference',0,.35,'magma')]:
        im=ax.imshow(values,aspect='auto',vmin=vmin,vmax=vmax,cmap=cmap)
        ax.set(title=title,yticks=range(5),yticklabels=range(1,6),xticks=range(8),xticklabels=bandlabels)
        ax.tick_params(axis='x',labelrotation=45);fig.colorbar(im,ax=ax,shrink=.8)
    fig.suptitle('Five F3 observations: common64Hz C; descriptive, unequal durations; no listening approval')
    fig.savefig(a.out/'comparison.png',dpi=140);plt.close(fig)
    r.update(result='five_F3_common_pitch_descriptive_comparisons_complete',common_root_hz=64,
        band_difference_dB=differences,complex_LR_difference=correlations,
        source_duration_unequal=True,realism_gate=False,acoustic_root_ratio=max(roots)/min(roots),
        legacy_root_boundary_exceeded=any(x>21600/(288*1.1) for x in roots),
        new_recordings_independent=False,physical_RPM_or_load=False,hearing=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
