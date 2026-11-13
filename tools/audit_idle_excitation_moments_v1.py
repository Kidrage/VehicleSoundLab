"""Independent scalar moments, transfer functions, RNG and complete audio oracle."""
import argparse
import math
import shutil
import sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','observation','render','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha


class IndependentRandom:
    def __init__(self,seed):self.state=seed or 1;self.spare=None
    def uniform(self):
        self.state^=self.state>>12
        self.state^=(self.state<<25)&((1<<64)-1)
        self.state^=self.state>>27
        self.state&=(1<<64)-1
        bits=((self.state*2685821657736338717)&((1<<64)-1))>>11
        return (bits+.5)/9007199254740992.
    def normal(self):
        if self.spare is not None:
            value=self.spare;self.spare=None;return value
        radius=math.sqrt(-2*math.log(self.uniform()));angle=math.tau*self.uniform()
        self.spare=radius*math.sin(angle)
        return radius*math.cos(angle)


def scalar_moments(x):
    output={name:[] for name in ['variance','cumulant4','excess','skew']}
    for column in x.T:
        n=len(column);mean=math.fsum(column)/n
        centered=[float(t)-mean for t in column]
        v=math.fsum(t*t for t in centered)/n
        fourth=math.fsum(t**4 for t in centered)/n
        output['variance'].append(v);output['cumulant4'].append(fourth-3*v*v)
        output['excess'].append(fourth/v**2-3)
        output['skew'].append(math.fsum(t**3 for t in centered)/n/v**1.5)
    return output


def compare_moments(actual,expected):
    for key in actual:
        assert np.allclose(actual[key],expected[key],rtol=1e-10,atol=1e-12),(key,actual,expected)


def sos_transfer(sos,size):
    z=np.exp(-2j*np.pi*np.arange(size//2+1)/size);out=np.ones(len(z),complex)
    for row in sos:
        out*=(row[0]+row[1]*z+row[2]*z*z)/(row[3]+row[4]*z+row[5]*z*z)
    return out


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running')
try:
    observed=load(a.observation/'report.json');rendered=load(a.render/'report.json');plan=observed['plan']
    assert observed['result']=='moment_candidate_compiled'
    assert rendered['result']=='sparse_excitation_candidates_pending_listening'
    for report in [observed,rendered]:
        for name,digest in report['sources'].items():assert sha(repo/name)==digest,name
    assert sha(a.observation/'report.json')==rendered['observation_sha256']
    assert sha(a.observation/'model.json')==rendered['model_sha256']
    profile=load(observed['profile_path']);assert sha(observed['profile_path'])==observed['profile_sha256']
    model=load(a.observation/'model.json');budget=load(a.observation/'moment_budget.json')
    impulse_data=np.load(a.observation/'effective_impulses.npz');h=impulse_data['impulses']
    maximum_filter_error=0.;maximum_wave_error=0.;maximum_band_error=0.
    # Polynomial transfer of every SOS, independent of scipy's recursive filter.
    sos=np.load(a.observation/'training.npz')['sos'];size=131072
    for b,s in enumerate(sos):
        transfer=sos_transfer(s,size)
        for i,kernel in enumerate(profile['kernels']):
            oracle=np.fft.irfft(transfer*np.fft.rfft(kernel['taps'],n=size),n=size)*kernel['gain']
            error=float(abs(oracle[:65536]-h[b,i]).max());maximum_filter_error=max(maximum_filter_error,error)
            assert error<1e-12
    for name,key in [('training','train'),('check','check')]:
        data=np.load(a.observation/(name+'.npz'));compare_moments(scalar_moments(data['filtered']),observed[key])
        length=1<<int(math.ceil(math.log2(len(data['audio'])+131072)))
        for b,s in enumerate(data['sos']):
            ir=np.fft.irfft(sos_transfer(s,131072),n=131072)
            y=np.fft.irfft(np.fft.rfft(data['audio'][:,0],n=length)*np.fft.rfft(ir,n=length),n=length)[:len(data['audio'])]
            error=float(abs(y[4800:-4800]-data['filtered'][:,b]).max());maximum_band_error=max(maximum_band_error,error)
            assert error<1e-11
    for row in observed['phase_controls']:
        data=np.load(a.observation/f"phase_{row['seed']}.npz")
        compare_moments(scalar_moments(data['filtered']),row['statistics'])
        original=np.load(a.observation/'training.npz')['audio']
        assert abs(abs(np.fft.rfft(original,axis=0))-abs(np.fft.rfft(data['audio'],axis=0))).max()<1e-10
    # The positive solution also satisfies the unconstrained square system.
    variance=np.array([[math.fsum(float(t)**2 for t in kernel) for kernel in row] for row in h]).sum(axis=1)
    main_stats=scalar_moments(np.column_stack([
        np.fft.irfft(np.fft.rfft(impulse_data['main'][:,0],n=524288)*sos_transfer(s,524288),n=524288)[:144000][4800:-4800]
        for s in sos]))
    variance+=np.array(main_stats['variance'])
    debt=np.array(observed['train']['excess'])*variance**2-np.array(main_stats['cumulant4'])
    matrix=np.array([[math.fsum(float(t)**4 for t in row[i]) for i in plan['kernel_indices']] for row in h])
    solved=np.linalg.solve(matrix/debt[:,None],np.ones(4))
    assert np.all(solved>=0) and np.allclose(solved,model['excess_input'],rtol=1e-9)
    assert np.allclose(3/(solved+3),model['probability'],rtol=1e-9)
    assert np.allclose(variance,budget['model_variance'],rtol=1e-9)
    frames=12*48000;count=frames+profile['warmup_frames'];nfft=1<<int(math.ceil(math.log2(count+8192)))
    main=np.zeros((frames,2));t=np.arange(frames)/48000
    for f,amp,phase in zip(profile['modal']['frequencies_hz'],profile['modal']['amplitude_LR'],profile['modal']['initial_phase_LR']):
        main+=np.real(np.exp(2j*np.pi*f*t[:,None]+1j*np.array(phase)[None,:])*np.array(amp))
    assert abs(main-sf.read(a.render/'main.wav',always_2d=True)[0]).max()<2e-8
    probabilities=dict(zip(plan['kernel_indices'],model['probability']))
    band_transfers=[sos_transfer(s,1<<20) for s in sos]
    for seed in plan['seeds']:
        outputs={amount:np.zeros_like(main) for amount in plan['amounts']}
        for i,kernel in enumerate(profile['kernels']):
            key=seed^((0x9E3779B97F4A7C15*(i+1))&((1<<64)-1))
            rng=IndependentRandom(key);mark=IndependentRandom(key^0xD1B54A32D192ED03)
            amp=IndependentRandom(key^0x94D049BB133111EB);prob=probabilities.get(i,1.)
            gaussian=np.array([rng.normal() for _ in range(count)])
            sparse=np.empty(count)
            for j in range(count):
                on=mark.uniform()<prob;z=amp.normal();sparse[j]=z/math.sqrt(prob) if on else 0.
            for amount in plan['amounts']:
                level=amount if i in probabilities else 0.
                excitation=math.sqrt(1-level)*gaussian+math.sqrt(level)*sparse
                whole=np.fft.irfft(np.fft.rfft(excitation,n=nfft)*np.fft.rfft(kernel['taps'],n=nfft),n=nfft)
                y=whole[profile['warmup_frames']:count]*kernel['gain']
                outputs[amount]+=y[:,None]*np.array([[1.,kernel['right_over_left']]])
        for amount,detail in outputs.items():
            tag=f'{round(amount*100):03d}_{seed}'
            for bus,expected in [('detail',detail),('mix',main+detail)]:
                actual,rate=sf.read(a.render/f'{bus}_{tag}.wav',always_2d=True)
                error=float(abs(actual-expected).max());maximum_wave_error=max(maximum_wave_error,error)
                assert rate==48000 and error<2e-8,(tag,bus,error)
            # Rebuild reported finite moments from the unrounded oracle and an
            # independent polynomial-transfer bandpass, not the observer code.
            spectrum=np.fft.rfft((main+detail)[:,0],n=1<<20)
            bands=np.column_stack([np.fft.irfft(spectrum*h,n=1<<20)[:frames][4800:-4800]
                                   for h in band_transfers])
            row=next(row for row in rendered['renders'] if row['tag']==tag)
            compare_moments(scalar_moments(bands),row['statistics'])
        print(dict(audited_seed=seed),flush=True)
    invariant=a.workspace/'baselines/idle_microtexture_c_v1/inputs'
    counts={}
    for filename in ['C_files_sha256.json','voice_files_sha256.json']:
        entries=load(invariant/filename)
        for name,digest in entries.items():assert sha(repo/name)==digest,name
        counts[filename]=len(entries)
    r.update(result='passed',complete_audio_candidates=9,max_wave_error_FS=maximum_wave_error,
             max_impulse_error=maximum_filter_error,max_bandpass_error=maximum_band_error,invariant_counts=counts,
             all9_finite_moment_reports_independently_verified=True,
             listening_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
