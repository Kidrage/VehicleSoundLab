"""Fit fixed LF colour and one beta envelope, retaining modeling mismatch."""
import argparse,csv,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal,optimize
from drive_evidence_v1.sources import read,sha
from catch_bloom_v1.measure import BANDS,RATE,powers,spectrum,rbj,pulse,envelope,band_gram
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
a.out.mkdir(parents=True,exist_ok=False)
for path in [Path(__file__),*list((repo/'tools/catch_bloom_v1').glob('*.py'))]:
    dst=a.out/'exact_sources'/path.relative_to(repo);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
r=dict(result='running',physical_source_separated=False,physical_clock_identified=False,human_accepted=False)
try:
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    t,power=powers(x);t+=33
    settling=(t>=38.53)&(t<=39.46);baseline=power[settling].mean(axis=0)
    # A deliberately coarse acoustic interval, not mechanical CATCH endpoints.
    first,stop=37.22,38.18;use=(t>=first+.05)&(t<=stop-.05);u=(t[use]-first)/(stop-first)
    excess=np.maximum(np.sqrt(power[use].sum(axis=1)/baseline.sum())-1,0)
    def beta_fit(values,uu):
        return optimize.least_squares(lambda v:v[2]*pulse(uu,v[0],v[1])-values,
            [1,1,max(values)],bounds=([.25,.25,0],[8,8,30]),xtol=1e-12,ftol=1e-12,gtol=1e-12)
    fit=beta_fit(excess,u);rise,fall,height=fit.x
    known=beta_fit(2.3*pulse(u,1.2,2.1),u)
    assert np.max(abs(known.x-[1.2,2.1,2.3]))<1e-8
    tones=np.column_stack([.2*np.sin(2*np.pi*70*np.arange(RATE)/RATE),.3*np.sin(2*np.pi*200*np.arange(RATE)/RATE)])
    _,kp=powers(tones);assert np.max(abs(kp.mean(axis=0)-[.01,.0225,0]))<1e-12
    f,tt,psd=spectrum(x);tt+=33
    # Derive broad fixed mode centres from positive power excess. The reference
    # changes pitch/source mixture: these are colour descriptors, not IR poles.
    excess_psd=np.maximum(psd[:,:, (tt>=first)&(tt<=stop)].mean(axis=(1,2))-
                          psd[:,:, (tt>=38.53)&(tt<=39.46)].mean(axis=(1,2)),0)
    modes=[]
    for lo,hi in BANDS:
        select=(f>=lo)&(f<hi);weights=excess_psd[select]
        centre=float(np.exp(np.sum(weights*np.log(f[select]))/np.sum(weights)))
        modes.append(dict(hz=centre,q=float(np.clip(centre/(hi-lo),.3,8))))
    build=a.workspace/'references/analysis/catch_bloom_v1/build2';proof=json.loads((build/'report.json').read_text())
    assert proof['result']=='isolated_adapter_built_and_checked'
    source=build/'renders/base2_dna.wav';dna,rate=sf.read(source,always_2d=True);assert rate==RATE
    with (build/'renders/base2_trace.csv').open() as stream:trace=list(csv.DictReader(stream))
    progress=np.repeat([float(row['catch_progress']) for row in trace],240)
    gate=np.repeat([int(row['lifecycle'])==3 for row in trace],240)
    env=envelope(progress,gate,rise,fall)
    component=np.array([signal.lfilter(*rbj(v['hz'],v['q']),dna,axis=0)*env[:,None] for v in modes])
    first_catch=np.flatnonzero(gate & (np.arange(len(gate))<2*RATE));start=int(first_catch[0]);end=int(first_catch[-1]+1)
    G=band_gram(np.concatenate([dna[None],component]),start,end)
    settle_G=band_gram(dna[None],round(1.3*RATE),round(2.1*RATE))[:,0,0]
    _,target=powers(x[round((first-33)*RATE):round((stop-33)*RATE)])
    target_ratio=target.mean(axis=0)/baseline
    def predict(gains):
        vector=np.r_[1,gains];return np.einsum('i,bij,j->b',vector,G,vector)/settle_G
    solved=optimize.least_squares(lambda v:10*np.log10(predict(v)/target_ratio),[1,1,1],bounds=(0,8),
        ftol=1e-12,xtol=1e-12,gtol=1e-12)
    for mode,gain in zip(modes,solved.x):mode['gain']=float(gain)
    y=dna+np.einsum('i,isc->sc',solved.x,component)
    tf,before=powers(dna);_,after=powers(y)
    # Independent Welch versus coherent Gram, protects the cross terms.
    fcheck,pcheck=signal.welch(y[start:end],RATE,nperseg=4800,noverlap=2400,axis=0,detrend=False)
    measured=np.array([pcheck[(fcheck>=lo)&(fcheck<hi)].sum(axis=0).mean()*10 for lo,hi in BANDS])
    assert np.max(abs(measured/(predict(solved.x)*settle_G)-1))<1e-12
    profile=a.out/'A cabin catch.cb'
    profile.write_text(f'VSL_CATCH_BLOOM 1 3 {rise:.17g} {fall:.17g} .005 .035\n'+
        ''.join(f'{v["hz"]:.17g} {v["q"]:.17g} {v["gain"]:.17g}\n' for v in modes),encoding='ascii')
    np.savez_compressed(a.out/'fit.npz',source_seconds=t,source_power=power,baseline=baseline,
        synthesized_seconds=tf,before=before,after=after,mode_signal=component,envelope=env,
        expected_delta=y-dna,excess=excess,progress=u,excess_fit=height*pulse(u,rise,fall))
    fig,axes=plt.subplots(2,1,figsize=(11,7),constrained_layout=True)
    for j,band in enumerate(BANDS):
        axes[0].plot(t,10*np.log10(np.maximum(power[:,j]/baseline[j],1e-12)),label=f'{band[0]}-{band[1]} Hz')
        axes[1].plot((tf-start/RATE)/.65,10*np.log10(np.maximum(before[:,j]/settle_G[j],1e-12)),ls=':',alpha=.6)
        axes[1].plot((tf-start/RATE)/.65,10*np.log10(np.maximum(after[:,j]/settle_G[j],1e-12)),label=f'{band[0]}-{band[1]} Hz')
    axes[0].set(xlim=(37.1,39.55),ylim=(-25,25),xlabel='A recording seconds',ylabel='Relative band power (dB)');axes[0].legend()
    axes[1].set(xlim=(-.1,1.5),ylim=(-25,25),xlabel='Engineering CATCH progress (not AV alignment)',ylabel='Relative band power (dB)');axes[1].legend()
    fig.savefig(a.out/'band_motion.png',dpi=140);plt.close(fig)
    r.update(result='coarse_support_candidate_fitted',profile=dict(path=profile.name,sha256=sha(profile),rise_shape=float(rise),
        fall_shape=float(fall),attack_seconds=.005,release_seconds=.035,modes=modes),source_dna_sha256=sha(source),
        acoustic_interval=[first,stop],settling_baseline_seconds=[38.53,39.46],
        fit_target_catch_to_settle_dB=(10*np.log10(target_ratio)).tolist(),
        original_catch_to_settle_dB=(10*np.log10(predict(np.zeros(3)))).tolist(),
        candidate_catch_to_settle_dB=(10*np.log10(predict(solved.x))).tolist(),
        fit_residual_dB=(10*np.log10(predict(solved.x)/target_ratio)).tolist(),
        temporal_amplitude_RMSE=float(np.sqrt(np.mean((height*pulse(u,rise,fall)-excess)**2))),
        known_beta_max_error=float(np.max(abs(known.x-[1.2,2.1,2.3]))),known_band_power_max_error=float(np.max(abs(kp.mean(axis=0)-[.01,.0225,0]))),
        limits=['One A cabin training observation; pitch/source/spatial mixture confounds the spectral ratio',
            'Shared smooth beta cannot reproduce all band-specific timing; no fast catch clock recovered',
            'Driver 0.65s interval is engineering, not a measured source time mapping',
            'Independent amount max1 is a candidate range, not an automatic production gain'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:r[k] for k in ('result','profile','fit_target_catch_to_settle_dB','original_catch_to_settle_dB','candidate_catch_to_settle_dB','fit_residual_dB')}))
