"""Direct source/decomposition/CSD audit and a zero-warmup actual-profile C oracle."""
import argparse
import csv
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','observation','fit','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for name in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[name]='2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
from sustain_osc_v1.oracle import Gaussian

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},trials=[])

def consume(path):r['inputs'][str(path)]=sha(path);return path

def spectral(audio,bands):
    window=np.hanning(2049)[:-1];p=np.zeros((1025,2));c=np.zeros(1025,complex);count=0
    for start in range(0,len(audio)-2048+1,512):
        z=np.fft.rfft(audio[start:start+2048]*window[:,None],axis=0)
        diagonal=abs(z)**2/(48000*math.fsum(window*window));diagonal[1:-1]*=2
        cross=z[:,0].conj()*z[:,1]/(48000*math.fsum(window*window));cross[1:-1]*=2
        p+=diagonal;c+=cross;count+=1
    assert count;p/=count;c/=count;hz=np.arange(1025)*48000/2048;result=[]
    for lo,hi in bands:
        keep=(hz>=lo)&(hz<hi)
        left,right=[math.fsum(p[keep,j])*48000/2048 for j in (0,1)];cross=sum(c[keep])*48000/2048
        result.append([[left,cross.conjugate()],[cross,right]])
    return np.array(result)

def unpack(rows):
    return np.array([[[p,c-1j*d],[c+1j*d,q]] for p,q,c,d in rows])

def differences(target,actual):
    return [dict(power_delta_db=(10*np.log10(b.diagonal().real/a.diagonal().real)).tolist(),
        complex_coherence_error=float(abs(b[1,0]/np.sqrt(b[0,0]*b[1,1])-a[1,0]/np.sqrt(a[0,0]*a[1,1])))) for a,b in zip(target,actual)]

try:
    for name in ('tools/audit_F3_detail_v1.py','tools/sustain_osc_v1/oracle.py','tools/research_archive_v1.py'):
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    # Exact Fourier-bin signed-cross fixture, checked before the real source.
    t=np.arange(16384)/48000;known=np.column_stack([.2*np.cos(2*np.pi*1500*t),.12*np.cos(2*np.pi*1500*t+.4)])
    known_matrix=spectral(known,[(1400,1600)])[0]
    assert abs(known_matrix[1,0]-.012*np.exp(.4j))<1e-14
    assert abs(known_matrix.diagonal().real-np.array([.02,.0072])).max()<1e-14
    r['known_before_source']=dict(signed_cross=True,band_power=True)
    observation=load(consume(a.observation/'report.json'));fit=load(consume(a.fit/'report.json'));plan=load(consume(repo/'research/F3_detail_v1_plan.json'))
    assert fit['result']=='fixed_additive_residual_candidate_rendered' and len(fit['models'])==10 and not fit['skipped']
    for folder in (a.observation,a.fit):
        report=load(folder/'report.json')
        for n,h in report['sources'].items():assert sha(repo/n)==h==sha(folder/'exact_sources'/n)
        for n,h in report['inputs'].items():assert sha(Path(n))==h
    frozen=a.workspace/'baselines/F3_lift_voice_v1';source=frozen/'evidence/fit2/F3 Sixth Before Upshift'
    original,rate=sf.read(consume(source/'normalized.wav'),always_2d=True);assert rate==48000
    blocks=original.reshape(14,1024,2)
    mean=np.array([[math.fsum(blocks[:,j,c])/14 for c in (0,1)] for j in range(1024)])
    coherent=np.tile(mean,(14,1));residual=original-coherent
    assert abs(coherent+residual-original).max()<1e-15
    errors=[]
    for name,expected in [('coherent',coherent),('residual',residual)]:
        actual,rate=sf.read(consume(a.observation/(name+'_canonical.wav')),always_2d=True)
        bound=.5*abs(np.spacing(actual.astype('float32')).astype(float))+2e-15
        assert np.all(abs(actual-expected)<=bound)
        errors.append(float(abs(actual-expected).max()))
    r['direct_cycle_mean_FLOAT_errors_FS']=errors
    # Independent scalar complex demodulation of each retained residual-power cycle.
    theta=2*np.pi*np.arange(1024)/1024;features=[];cp=plan['cyclic']
    for band in plan['bands_hz']:
        sos=signal.butter(4,np.array(band)*46.875/fit['root_hz'],fs=48000,btype='bandpass',output='sos')
        wave=signal.sosfiltfilt(sos,residual,axis=0).reshape(14,1024,2)[2:12]
        level=np.mean(wave**2,axis=(0,1));beta=np.zeros((10,2,4),complex)
        for n in range(10):
            for c in (0,1):
                for k in range(1,5):
                    z=wave[n,:,c]**2*np.exp(-1j*k*theta)
                    beta[n,c,k-1]=2*complex(math.fsum(z.real),math.fsum(z.imag))/1024/max(level[c],1e-12)
        features.append(beta)
    features=np.array(features)
    def score(features):
        return np.real(features[:,::2].mean(axis=1)*features[:,1::2].mean(axis=1).conj()).mean(axis=(1,2))
    values=score(features);rng=np.random.default_rng(cp['seed']);null=[]
    for _ in range(cp['permutations']):
        phase=rng.uniform(0,2*np.pi,10);changed=features.copy()
        for n in range(10):
            for k in range(4):changed[:,n,:,k]*=np.exp(-1j*phase[n]*(k+1))
        null.append(max(score(changed)))
    saved=observation['source_dependence'];assert abs(np.array(null)-saved['max_null']).max()<1e-10
    for value,row in zip(values,saved['bands']):
        assert abs(value-row['train_heldout_cross_statistic'])<1e-10
        pvalue=(1+sum(v>=value for v in null))/257
        assert pvalue==row['familywise_p']
    r['cyclic_residual_statistics_independently_reproduced']=True
    bands=plan['bands_hz'];ref,rate=sf.read(consume(source/'reference.wav'),always_2d=True)
    old,rate=sf.read(consume(source/'DNA_1.wav'),always_2d=True)
    main,rate=sf.read(consume(a.fit/'main32.wav'),always_2d=True)
    assert main.shape==(1536000,2) and np.array_equal(main[:len(old)],old)
    target=spectral(ref,bands);current=spectral(old[24000:],bands);budget=load(consume(a.fit/'matrices.json'))
    for key,value in [('target',target),('DNA',current),('debt',target-current)]:assert abs(value-unpack(budget[key])).max()<1e-14
    # Parse every numeric parameter consumed by the actual C loader independently.
    profile=a.fit/'F3_before_upshift.sres';tokens=iter(profile.read_text(encoding='ascii').split())
    def take(n):return [next(tokens) for _ in range(n)]
    head=take(6);assert head[:5]==['VSL_STEREO_RESONANCE','1','48000','10','96000']
    for model in fit['models']:
        order,sections,lo,hi,gain=map(float,take(5));order=int(order);sections=int(sections)
        assert [lo,hi]==model['band_hz'] and gain==model['gain']
        for n,key,shape in [(order*4,'a',(order,2,2)),(4,'noise',(2,2)),(sections*6,'sos',(sections,6)),((2*order)**2,'certificate',(2*order,2*order))]:
            values=np.array(list(map(float,take(n)))).reshape(shape);assert np.array_equal(values,np.array(model[key]))
        coeff=np.array(model['a']);f=np.zeros((2*order,2*order));f[:2]=coeff.transpose(1,0,2).reshape(2,2*order);f[2:,:-2]=np.eye(2*order-2)
        cert=np.array(model['certificate']);margin=cert-f.T@cert@f
        assert min(np.linalg.eigvalsh(cert))>0 and min(np.linalg.eigvalsh((margin+margin.T)/2))>0
        assert max(abs(np.linalg.eigvals(f)))<.9998
    assert next(tokens,None) is None
    # Actual full10-band parameters through unchanged C versus non-circular Python history.
    # Zero warmup is an explicitly separate diagnostic profile, not the candidate.
    text=profile.read_text(encoding='ascii');header,body=text.split('\n',1);fields=header.split();fields[4]='0'
    diagnostic=a.out/'zero_warmup_diagnostic.sres';diagnostic.write_text(' '.join(fields)+'\n'+body,encoding='ascii',newline='\n')
    output=a.out/'actual_profile_oracle.f64';seed=8121907;frames=1536
    argv=[str(a.fit/'bin/stereo_resonance_probe.exe'),str(diagnostic),str(output),str(seed),str(frames),'1']
    done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=60);(a.out/'C_oracle.log').write_bytes(done.stdout+done.stderr)
    assert done.returncode==0;r['oracle_command']=argv
    expected=np.zeros((frames,2))
    for b,model in enumerate(fit['models']):
        coefficients=np.array(model['a']);noise=np.array(model['noise']);order=len(coefficients)
        generators=[Gaussian(seed^((0x9e3779b97f4a7c15*(2*b+c+1))&((1<<64)-1))) for c in (0,1)]
        white=np.array([[g.next() for g in generators] for _ in range(frames)]);history=np.zeros((frames+order,2))
        for n in range(frames):
            history[n+order]=noise@white[n]
            for j in range(order):history[n+order]+=coefficients[j]@history[n+order-1-j]
        expected+=model['gain']*signal.sosfilt(np.array(model['sos']),history[order:],axis=0)
    actual=np.fromfile(output,dtype='<f8').reshape(-1,2);cerror=float(abs(actual-expected).max());assert cerror<2e-11
    r['C_actual_profile_zero_warmup_oracle_error_FS']=cerror
    theory=unpack(budget['expected_detail']);fig,axes=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    baseline=differences(target,spectral(main[24000:384000],bands))
    for seed in plan['detail_seeds']:
        detail=np.fromfile(consume(a.fit/f'detail32_{seed}.f64'),dtype='<f8').reshape(-1,2)
        assert detail.shape==main.shape and np.isfinite(detail).all()
        measured=spectral(detail,bands);long=differences(theory,measured)
        assert max(abs(v) for row in long for v in row['power_delta_db'])<.75
        assert max(row['complex_coherence_error'] for row in long)<.08
        mixed=main+detail;wave,rate=sf.read(consume(a.fit/f'candidate_{seed}.wav'),always_2d=True)
        assert np.array_equal(wave,mixed[:384000].astype('float32').astype('float64'))
        short=differences(target,spectral(mixed[24000:384000],bands))
        r['trials'].append(dict(seed=seed,C_theory=long,mixed_vs_reference=short))
        axes[0].plot(range(10),[row['power_delta_db'][0] for row in short],'.-',label=f'Candidate{seed}, L')
    axes[0].plot(range(10),[row['power_delta_db'][0] for row in baseline],'k.--',label='Unchanged DNA, L')
    axes[0].set(ylabel='Power difference dB',xticks=range(10),xticklabels=[f'{lo/1000:g}-{hi/1000:g}' for lo,hi in bands],xlabel='Native acoustic band kHz',title='F3 short training reference vs generated sound; not realism validation')
    axes[0].axhline(0,color='gray',lw=.7);axes[0].legend(ncol=2,fontsize=8)
    axes[1].bar(range(10),[row['familywise_p'] for row in saved['bands']]);axes[1].axhline(.01,color='red',ls=':')
    axes[1].set(ylabel='Descriptive familywise p',xlabel='Residual power / shared acoustic cycle; no physical source label',xticks=range(10),xticklabels=[f'{lo/1000:g}-{hi/1000:g}' for lo,hi in bands])
    fig.savefig(a.out/'diagnostic.png',dpi=130);plt.close(fig)
    index=frozen/'source/handoff/C文件索引.csv';rows=list(csv.DictReader(index.open(encoding='utf-8-sig')))
    assert len(rows)==647 and all(sha(repo/v['文件'])==v['SHA-256'] for v in rows)
    voices=load(frozen/'inputs/voice_files_sha256.json');assert len(voices)==74 and all(sha(repo/n)==h for n,h in voices.items())
    r.update(result='passed',protected_C_H_exact=647,protected_voice_parameters_exact=74,
        profile_roundtrip_exact=True,stability_certificates=True,main8s_exact=True,runtime_changed=False,hearing=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print({key:r.get(key) for key in ('result','C_actual_profile_zero_warmup_oracle_error_FS','protected_C_H_exact')})
