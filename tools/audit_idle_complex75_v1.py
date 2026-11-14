"""Independent native extraction, joint FIR, Gaussian law and all finite render checks."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','render','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal,linalg,interpolate
from numpy.polynomial.hermite import hermgauss
from research_archive_v1 import load,save,sha
from idle_short_budget_v1.independent import design,project

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
shutil.copy2(repo/'tools/idle_short_budget_v1/independent.py',a.out/'executed_independent.py')
r=dict(result='running',fit_sha256=sha(a.fit/'report.json'),render_sha256=sha(a.render/'report.json'),errors={},extractions=[],renders=[])


def check(key,x,y,gate=1e-10):
    d=float(np.max(abs(np.asarray(x)-np.asarray(y))));r['errors'][key]=max(d,r['errors'].get(key,0.))
    assert d<=gate,(key,d,gate)


def root(C,inverse=False):
    e,U=linalg.eigh(C);active=e>np.finfo(float).eps*len(e)*max(float(e.max()),0.)
    s=np.zeros_like(e);s[active]=1/np.sqrt(e[active]) if inverse else np.sqrt(e[active])
    return U@np.diag(s)@U.T


def curves(h):
    h=np.asarray(h);return np.array([sum(h[j]@h[j+k].T for j in range(len(h)-k)) for k in range(4)])


def tables(h,step,kind):
    c=curves(h);u=np.arange(step)/step
    w=np.array([[-.5*v+v*v-.5*v**3,1-2.5*v*v+1.5*v**3,.5*v+2*v*v-1.5*v**3,-.5*v*v+.5*v**3] for v in u])
    raw=np.zeros((step,len(c[0]),len(c[0])))
    for f in range(step):
        for i in range(4):
            for j in range(4):raw[f]+=w[f,i]*w[f,j]*(c[j-i] if j>=i else c[i-j].T)
    if kind=='symmetric':T=np.array([root(c[0])@root(v,True) for v in raw])
    else:T=np.array([linalg.solve_triangular(linalg.cholesky(v,lower=True),linalg.cholesky(c[0],lower=True).T,trans='T',lower=True).T for v in raw])
    check('all_fraction_covariance_'+kind,np.array([t@v@t.T for t,v in zip(T,raw)]),np.broadcast_to(c[0],raw.shape),1e-12)
    return w,T,c,raw


def native(values,w,T,step,frames):
    out=np.empty((frames,values.shape[1]))
    for first in range(0,frames,24000):
        ix=np.arange(first,min(frames,first+24000));k=ix//step;f=ix%step
        raw=np.sum(values[k[:,None]+np.arange(1,5)]*w[f,:,None],axis=1)
        out[first:first+len(ix)]=np.matmul(T[f],raw[:,:,None])[:,:,0]
    return out


def filtered_nodes(h,seed,seconds,rate,key):
    h=np.asarray(h);warm=len(h)-1;count=int(seconds*rate)+5
    white=np.random.Generator(np.random.PCG64(seed^key)).standard_normal((count+warm,h.shape[2]))
    y=np.column_stack([sum(np.convolve(white[:,j],h[:,i,j],mode='valid') for j in range(h.shape[2])) for i in range(h.shape[1])])
    return y,white


def extract(audio,freq,z,folder,label):
    A=design(len(audio),freq,z);residual,beta=project(audio[:,None],A);ref=complex(beta[1,0],-beta[14,0])
    h=signal.firwin(24001,15,fs=48000,window=('kaiser',8.6))
    filtered=signal.fftconvolve(2*residual[:,0]*z[:,0].conj(),h,mode='same')
    b=1+filtered[np.arange(12000,132000,480)]/ref
    assert abs(b).min()>0 and abs(np.angle(b)).max()<np.pi-.05
    raw=np.column_stack((np.log(abs(b)),np.angle(b)));latent=raw-raw.mean(axis=0)
    if folder:
        with np.load(folder/(label+'.npz')) as f:
            for key,value in [('reference',ref),('beta',beta),('native_residual',residual[:,0]),('filtered',filtered),('relative_envelope',b),('raw_latent',raw),('latent',latent),('taps',h),('mean',raw.mean(axis=0))]:check('extraction_'+key,value,f[key])
    r['extractions'].append(label);return latent,b


try:
    fit=load(a.fit/'report.json');render=load(a.render/'report.json')
    assert fit['result']=='source_native_complex75_fitted_pending_audit' and render['result']=='finite_complex75_candidate_pending_audit'
    for folder,report in [(a.fit,fit),(a.render,render)]:
        for path,digest in report['inputs'].items():assert sha(path)==digest
        for path,digest in report['sources'].items():assert sha(folder/'exact_sources'/path)==digest==sha(repo/path)
    # All saved known native controls, independent weighted QR and full convolution.
    with np.load(a.fit/'known.npz') as f:
        freq=f['frequencies'];z=f['phasors'];beta=f['beta'];A=design(len(z),freq,z)
        check('known_audio',A@beta,f['base_audio'])
        constant,_=extract(f['base_audio'],freq,z,None,'known_constant');check('known_constant',constant,0,1e-10)
        fm,_=extract(design(len(z),freq,f['FM_phasors'])@beta,freq,f['FM_phasors'],None,'known_FM');check('known_FM',fm,0,1e-10)
        latent,b=extract(f['complex_audio'],freq,z,None,'known_complex');check('known_exact_filtered_complex',b,f['expected_relative_envelope'])
        check('known_complex_latent',latent,f['measured_latent'])
        t=np.arange(len(z))/48000;neighbor,_=extract(A@beta+.01*np.cos(2*np.pi*(freq[1]+7.2)*t),freq,z,None,'known_neighbor')
        assert neighbor[:,0].std()>.01
    # Independent full covariance interpolation + Gaussian integrals, including rank deficient cases.
    x,q=hermgauss(9);zz=np.stack(np.meshgrid(x*np.sqrt(2),x*np.sqrt(2),indexing='ij'),axis=-1).reshape(-1,2);q=np.outer(q,q).ravel()/np.pi
    for name in ['delayed','AM','phase','zero','source']:
        h=np.zeros((8,2,2))
        if name=='delayed':h[0,0,0]=.12;h[2,1,0]=.07;h[0,1,1]=.08
        elif name=='AM':h[0,0,0]=.12
        elif name=='phase':h[0,1,0]=.12
        elif name=='source':h=np.array(load(a.fit/'model.json')['taps'])
        w,T,c,raw=tables(h,480,'symmetric');C=c[0];v=zz@root(C).T;g=np.exp(v[:,0]-C[0,0]+1j*(v[:,1]-C[0,1]))
        check('Gaussian_power_'+name,q@abs(g)**2,1,1e-10)
        check('Gaussian_mean_'+name,q@g,np.exp(-.5*np.trace(C)),1e-10)
        check('Gaussian_second_complex_'+name,q@g**2,np.exp(-2*C[1,1]+2j*C[0,1]),1e-10)
    rootpath=a.workspace/'baselines';profile=load(rootpath/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json');freq=np.array(profile['modal']['frequencies_hz'])
    source=rootpath/'idle_conditioned_detail_v1/evidence/observe1'
    for part in ['train','check']:
        with np.load(source/(part+'.npz')) as f:latent,b=extract(f['audio'][:,0],freq,f['phasors'],a.fit,part)
        if part=='train':train=latent
    # TRAIN only spectral fit. CHECK is never passed into this reconstruction.
    w=np.hanning(65)[:-1];sections=[train[j:j+64]*w[:,None] for j in range(0,187,32)];assert len(sections)==6
    Z=np.array([np.fft.rfft(section,n=128,axis=0) for section in sections])
    factors=[]
    for f in range(65):
        S=sum(np.outer(z[f],z[f].conj()) for z in Z)/(6*np.dot(w,w));e,U=linalg.eigh(S)
        factors.append(U@np.diag(np.sqrt(np.maximum(e,0)))@U.conj().T)
    h=np.roll(np.fft.irfft(factors,n=128,axis=0),64,axis=0);C=train.T@train/250
    colour=root(C)@root(curves(h)[0],True);h=np.array([colour@v for v in h]);model=load(a.fit/'model.json')
    check('fit_all_taps',h,model['taps'],1e-12);check('fit_covariance',C,model['covariance'],1e-12);check('fit_colour',colour,model['colour'],1e-12)
    w,T,c,raw=tables(h,480,'symmetric')
    with np.load(a.fit/'interpolation.npz') as f:
        for key,value in [('weights',w),('transform',T),('covariance',c[0]),('raw',raw)]:check('all480_'+key,value,f[key],1e-12)
    old=load(rootpath/'idle_phase_amplitude_v1/evidence/render2/model.json');ow,oT,oc,_=tables(old['taps'],960,'cholesky')
    amplitudes=np.array(load(rootpath/'idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'])[0]
    delta=np.diff(np.array(profile['modal']['initial_phase_LR'])[1])[0]
    phasepath=rootpath/'idle_phase_recipe_v1/evidence/render2';pm=load(phasepath/'model.json')
    matrix=np.array([[-1.,-1.,1.],[3.,-2.,0.]]);right=linalg.lstsq(matrix,np.eye(2))[0]
    frames=1152000;t=np.arange(frames)/48000
    for row in render['renders']:
        seed=row['seed'];values,white=filtered_nodes(h,seed,24,100,0xC075A4F18E29)
        independent,_=filtered_nodes(old['taps'],seed^0x7C75B41D93,24,50,0xA1D1E5A39B47)
        with np.load(a.render/row['driver_file']) as f:
            assert sha(a.render/row['driver_file'])==row['driver_sha256']
            check('fresh_complex_white',white,f['complex_white'],0);check('fresh_complex_nodes',values,f['complex_nodes'],1e-12)
            check('independent_old_nodes',independent,f['independent_old_nodes'],1e-12);drivers=f['drivers']
        original_entry=next(v for v in load(rootpath/'idle_local_partition_v1/evidence/render1/report.json')['renders'] if v['seed']==seed)
        with np.load(rootpath/'idle_local_partition_v1/evidence/render1'/original_entry['nodes_file']) as f:original=f['nodes']
        old_gain=np.exp(native(original,ow,oT,960,frames)[:,0]-oc[0,0,0])
        control=np.exp(native(independent,ow,oT,960,frames)[:,0]-oc[0,0,0])
        x=native(values,w,T,480,frames);g=np.exp(x[:,0]-C[0,0]+1j*(x[:,1]-C[0,1]))
        check('all_native_drivers',np.column_stack((old_gain,control,g.real,g.imag)),drivers,1e-10)
        with np.load(phasepath/f'motion_{seed}.npz') as f:
            coordinate=interpolate.CubicSpline((np.arange(len(f['coordinate_nodes']))-2)/200,f['coordinate_nodes'],bc_type='natural')(t)
        z=np.exp(1j*(2*(pm['carrier_phase_rad']+2*np.pi*pm['carrier_hz']*t)+coordinate@right[0]))
        carriers=z[:,None]*np.exp(1j*delta*np.arange(2))[None,:]
        changes=dict(independent_old=amplitudes*carriers.real*(control-old_gain)[:,None],
            complex75=amplitudes*((carriers*g[:,None]).real-carriers.real*old_gain[:,None]))
        finite={}
        for branch,change in changes.items():
            actuals={};basewaves={}
            for bus in ['mix','main']:
                before=row['baseline'][bus];assert sha(before['file'])==before['sha256'];base,rate=sf.read(before['file'],always_2d=True)
                entry=row['files'][branch+'_'+bus];file=a.render/entry['file'];assert sha(file)==entry['sha256']
                actual,rate=sf.read(file,always_2d=True);assert rate==48000 and actual.shape==(frames,2)
                check('all12_WAVs',base+change,actual,1e-7);assert abs(actual).max()<.85
                check('finite_report_RMS',np.sqrt(np.mean((base+change)**2)),entry['rms'],1e-10)
                actuals[bus]=actual;basewaves[bus]=base
            check('detail_invariance_FLOAT',actuals['mix']-actuals['main'],basewaves['mix']-basewaves['main'],1e-7)
            finite[branch]=dict(rms=float(np.sqrt(np.mean(actuals['mix']**2))),peak=float(abs(actuals['mix']).max()))
        r['renders'].append(dict(seed=seed,finite=finite));save(a.out/'report.json',r)
    r.update(result='passed',all3seeds_full24seconds=True,all12_audio_rebuilt=True,source_train_only_fit=True,
        independent_old_full3D_stream_rebuilt=True,all480_joint_covariances_checked=True,gain_power_not_finite_take_RMS=True,
        source_separation_claimed=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],errors=r['errors'],renders=r['renders']),flush=True)
