"""Independent complete QR, response interpolation and resolution-statistics audit."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import linalg,signal,fft
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},QR_factorizations=0,cases=[],transfer=[])
centres=16800+np.arange(116)*960;S=np.array([1,2,4]);responses={}


def check(key,x,y,gate=1e-10,relative=0):
    x=np.asarray(x);y=np.asarray(y);d=float(abs(x-y).max());r['errors'][key]=max(r['errors'].get(key,0.),d)
    assert d<=gate+relative*float(abs(y).max()),(key,d)


def measured(audio,freq):
    n=len(audio);multiplier=np.zeros(n);multiplier[0]=multiplier[n//2]=1;multiplier[1:n//2]=2;out=[]
    for hz in freq[S]:
        sos=signal.iirfilter(4,[hz-10,hz+10],btype='bandpass',ftype='butter',fs=48000,output='sos')
        v=signal.sosfiltfilt(sos,audio);z=fft.ifft(fft.fft(v)*multiplier);out.append(z/abs(z))
    return np.column_stack(out)


def QR(audio,freq,z,ms,response_reference=None):
    t=np.arange(len(audio))/48000;A=np.ones((len(audio),27))
    for j,hz in enumerate(freq):
        v=z[:,list(S).index(j)] if j in S else np.exp(2j*np.pi*hz*t)
        A[:,j]=v.real;A[:,j+13]=v.imag
    n=int(ms*48);w=np.hanning(n+1)[:-1];sqrtw=np.sqrt(w);out=[];condition=[];response=[]
    for centre in centres:
        first=centre-n//2;slab=A[first:first+n]*sqrtw[:,None];Q,R=np.linalg.qr(slab,mode='reduced')
        b=linalg.solve_triangular(R,Q.T@(sqrtw*audio[first:first+n]))
        out.append(b[:13]-1j*b[13:26]);condition.append(np.linalg.cond(R));r['QR_factorizations']+=1
        if response_reference is not None:
            # Real coefficient of75Hz, with exact pre-existing native carrier amplitude.
            unit=np.zeros(27);unit[1]=1
            P=linalg.solve_triangular(R.T,unit,lower=True)@Q.T*sqrtw
            response.append(P*z[first:first+n,0].real*response_reference)
    return np.array(out),np.array(condition),np.array(response)


def covariance(c,ref):
    z=c[:,S]/ref;v=np.column_stack((z.real,z.imag));v-=v.mean(axis=0);curves=[]
    for lag in range(-25,26):
        indices=np.arange(max(0,-lag),min(len(v),len(v)-lag))
        curves.append(np.einsum('ti,tj->ij',v[indices],v[indices+lag])/len(indices))
    f,power=signal.periodogram(v,fs=50,window=np.hanning(len(v)+1)[:-1],detrend=False,scaling='density',axis=0)
    power*=50/len(v)
    return np.array(curves),power


try:
    run=load(a.input/'report.json');assert run['result']=='idle_aperture_transfer_and_resolution_observed'
    for path,digest in run['sources'].items():assert sha(a.input/'exact_sources'/path)==digest
    for path,digest in run['inputs'].items():assert sha(path)==digest
    root=a.workspace/'baselines';freq=np.array(load(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')['modal']['frequencies_hz'])
    frozen=root/'idle75_clock_v1/evidence/fit2';previous=load(frozen/'report.json');stream_lookup={row['seed']:row for row in previous['streams']}
    ref=load(root/'idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'][0][0]
    with np.load(a.input/'known.npz') as f:
        for ms in [50,100,200]:
            coefficient,condition,_=QR(f['audio'],freq,f['phasors'],ms)
            check('all_known_QR',coefficient,f[str(ms)]);check('model_exact_FM',coefficient,np.tile(f['expected'],(116,1)))
    oldroot=root/'idle_variation_budget_v1/evidence/observe1';old_lookup={row['label']:row for row in load(oldroot/'report.json')['cases']}
    data={}
    for row in run['cases']:
        label=row['label'];meta=row['metadata'];ms=row['window_ms']
        if label not in data:
            if meta['kind']=='generated':
                with np.load(frozen/stream_lookup[meta['seed']]['file']) as f:audio=f['baseline_mix'];z=f['phasors']
                if meta['phase_basis']=='measured_acoustic':z=measured(audio,freq)
                oldlabel=f'generated_{meta["seed"]}_1.0_0_{meta["phase_basis"]}'
            else:
                origin=root/'idle_conditioned_detail_v1/evidence/observe1'
                with np.load(origin/(meta['part']+'.npz')) as f:audio=f['audio'][:,0];z=f['phasors']
                if meta['seed'] is not None:
                    amplitude=np.fft.rfft(audio);phase=np.random.default_rng(meta['seed']).uniform(-np.pi,np.pi,len(amplitude));phase[0]=phase[-1]=0
                    audio=np.fft.irfft(amplitude*np.exp(1j*phase),n=len(audio))
                    with np.load(origin/f'{meta["part"]}_phase_{meta["seed"]}.npz') as f:z=f['phasors']
                oldlabel=label
            data[label]=(audio,z,oldlabel)
        audio,z,oldlabel=data[label];file=a.input/row['file'];assert sha(file)==row['sha256']
        make_response=meta['kind']=='generated' and meta['phase_basis']=='procedural' and ms==200
        coefficient,condition,h=QR(audio,freq,z,ms,ref if make_response else None)
        if make_response:responses[meta['seed']]=h
        with np.load(file) as f:
            check('all42_QR',coefficient,f['coefficients']);check('all_conditions',condition,f['condition'],1e-7,1e-8)
            cov,power=covariance(coefficient,f['reference']);check('all51signed_covariance',cov,f['covariance'],1e-9)
            check('all_temporal_PSD',power,f['temporal_psd'],1e-10)
            check('all_report_std',np.sqrt(np.diag(cov[25])),row['std'],1e-9)
            check('all_report_rho',np.array([np.diag(cov[25+lag])/np.diag(cov[25]) for lag in [5,10,25]]),row['rho'],1e-8,2e-7)
        if ms==200:
            old=old_lookup[oldlabel]
            with np.load(oldroot/old['file']) as f:check('all14_frozen200ms_coefficients',coefficient,f['coefficients'][:,0,:])
        r['cases'].append(dict(label=label,window_ms=ms));save(a.out/'report.json',r)
    for row in run['transfer']:
        seed=row['seed'];h=responses[seed]/ref
        with np.load(frozen/stream_lookup[seed]['file']) as f:check('all348_cached_native_response',h,(f['response_h']/ref).real)
        with np.load(a.input/f'transfer_{seed}.npz') as f:
            for control in row['controls']:
                frequency=control['temporal_hz'];t=np.arange(144000)/48000
                q=np.array([np.cos(2*np.pi*frequency*t),np.sin(2*np.pi*frequency*t)]).T;first=[];second=[]
                for j,start in enumerate(centres-4800):first.append(h[j]@q[start:start+9600])
                first=np.array(first)
                for j in range(10,106):
                    t=np.arange(centres[j]-4800,centres[j]+4800)/48000;p=(t-centres[0]/48000)*50;k=np.floor(p).astype(int);u=p-k
                    w=np.array([-.5*u*(1-u)**2,1+u*u*(1.5*u-2.5),u*(.5+u*(2-1.5*u)),.5*u*u*(u-1)]).T
                    lifted=np.zeros((9600,2))
                    for i in range(4):lifted+=w[:,i,None]*first[k+i-1]
                    second.append(h[j]@lifted)
                native=np.array([np.cos(2*np.pi*frequency*centres[10:106]/48000),np.sin(2*np.pi*frequency*centres[10:106]/48000)]).T
                second=np.array(second)
                for key,value in [('native',native),('first',first),('second',second)]:check('all12_two_pass_arrays',value,f[f'{frequency}_{key}'])
                variance=lambda x:float(np.mean(np.sum((x-x.mean(axis=0))**2,axis=1))/2)
                v0,v1,v2=[variance(x) for x in [native,first[10:106],second]]
                for key,value in [('native_variance',v0),('first_variance',v1),('second_variance',v2),('first_power_ratio',v1/v0),('second_power_ratio',v2/v0),('second_over_first_power',v2/v1)]:
                    check('all12_transfer_metrics',value,control[key])
                r['transfer'].append(dict(seed=seed,temporal_hz=frequency))
    assert r['QR_factorizations']==5220 and len(r['cases'])==42 and len(r['transfer'])==12
    r.update(result='complete_idle_aperture_QR_and_transfer_independently_checked',new_source_fit=False,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],QR=r['QR_factorizations'],errors=r['errors']),flush=True)
