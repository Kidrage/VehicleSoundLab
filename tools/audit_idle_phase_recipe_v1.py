"""Independent phase recursion/trigonometry and direct FIR checks for every saved idle bus."""
import argparse
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ['workspace','input','out']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import interpolate,linalg,signal
from research_archive_v1 import load,save,sha

M=np.array([[-1.,-1.,1.],[3.,-2.,0.]])
H=np.array([2.,3.,5.]);RIGHT=np.linalg.lstsq(M,np.eye(2),rcond=None)[0]
INDICES=[1,2,4]

def independent_nodes(model,seed,count):
    rng=np.random.Generator(np.random.PCG64(seed ^ 0x1DB87B43124A))
    state=np.linalg.cholesky(model['stationary_covariance'])@rng.standard_normal(4)
    eps=np.random.Generator(np.random.PCG64(seed ^ 0xA4F91CD27855)).standard_normal((count-1,2))
    root=np.linalg.cholesky(model['innovation_covariance']);matrix=np.asarray(model['transition'])
    result=np.empty((count,2));result[0]=state[:2]
    for j in range(1,count):
        old=state.copy()
        for k in range(4):state[k]=sum(float(matrix[k,c]*old[c]) for c in range(4))
        state[:2]+=root@eps[j-1];result[j]=state[:2]
    return result+model['coordinate_center']

def phases(model,motion,t):
    u=motion(t);carrier=model['carrier_phase_rad']+2*np.pi*model['carrier_hz']*t
    return carrier[:,None]*H+u@RIGHT.T

def powers(theta,law):
    angle=np.column_stack((theta,theta[:,1]-theta[:,0],theta[:,2]-theta[:,0],theta[:,2]-theta[:,1]))
    c=np.asarray(law['coefficients']);eta=np.tile(c[0],(len(theta),1))
    for j in range(6):eta+=np.cos(angle[:,j,None])*c[j+1]+np.sin(angle[:,j,None])*c[j+7]
    return np.exp(eta)

def phase_stats(values):
    # ALL501 linear-overlap lag points, no circular segment joining or source PCM playback.
    n=len(values);center=values-values.mean(axis=0);lags=np.arange(501)
    curves=np.empty((2,2,len(lags)))
    for i in range(2):
        for j in range(2):
            corr=signal.correlate(center[:,j],center[:,i],mode='full',method='fft')
            curves[i,j]=corr[n-1+lags]/(n-lags)
    return dict(mean=values.mean(axis=0).tolist(),std=values.std(axis=0).tolist(),
      circular_resultant=abs(np.exp(1j*values).mean(axis=0)).tolist(),
      covariance=(center.T@center/n).tolist(),quantiles=np.quantile(values,[0,.01,.05,.5,.95,.99,1],axis=0).tolist()),curves

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',checks=[],phase_observations=[])
try:
    report=load(a.input/'report.json');assert report['result']=='new_stationary_idle_phase_audio_pending_independent_audit'
    for name,digest in report['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    for row in report['inputs'].values():assert sha(row['path'])==row['sha256']
    profile=load(report['inputs']['profile']['path']);model=load(a.input/'model.json');law=report['law']
    assert sha(a.input/'model.json')==report['model_sha256']
    matrix=np.asarray(model['transition']);P=np.asarray(model['stationary_covariance']);Q=np.zeros((4,4))
    Q[:2,:2]=model['innovation_covariance'];lyap=float(abs(P-matrix@P@matrix.T-Q).max());assert lyap<1e-11
    assert abs(np.linalg.eigvals(matrix)).max()<1 and np.linalg.eigvalsh(P).min()>0
    assert abs(M@RIGHT-np.eye(2)).max()<1e-14 and abs(M@H).max()==0
    # An explicitly unstable fixture is rejected by the same strict stability condition.
    unstable=np.diag([1.001,.7,.4,.2]);assert not bool(abs(np.linalg.eigvals(unstable)).max()<1)
    r['known']=dict(lyapunov_residual=lyap,positive_stationary_covariance=True,unstable_fixture_rejected=True)
    amp=np.asarray(profile['modal']['amplitude_LR']);f=np.asarray(profile['modal']['frequencies_hz']);ph=np.asarray(profile['modal']['initial_phase_LR'])
    for row in report['renders']:
        seed=row['seed'];frames=row['seconds']*48000
        with np.load(a.input/row['motion_file']) as data:archive={k:data[k] for k in data.files}
        assert sha(a.input/row['motion_file'])==row['motion_sha256']
        actual=archive['coordinate_nodes'];expected=independent_nodes(model,seed,len(actual))
        recur=float(abs(actual-expected).max());assert recur<1e-10
        x=(np.arange(len(expected))-2)/200
        motion=interpolate.make_interp_spline(x,expected,k=3,bc_type='natural')
        audio={}
        for name,item in row['files'].items():
            path=a.input/item['file'];assert sha(path)==item['sha256'];y,rate=sf.read(path,always_2d=True)
            assert rate==48000 and len(y)==frames and np.isfinite(y).all() and abs(y).max()<1
            assert float(abs(y).max())==item['peak'];audio[name]=y
        errors=dict(old_main=0.,new_main=0.,q_free=0.,q_related=0.,mix_identity=0.)
        for start in range(0,frames,48000):
            stop=min(frames,start+48000);t=np.arange(start,stop)/48000
            free=2*np.pi*t[:,None]*f[INDICES]+ph[INDICES,0]
            related=phases(model,motion,t)
            old=np.zeros((len(t),2));new=np.zeros_like(old)
            for index in range(len(f)):
                for channel in range(2):
                    v=amp[index,channel]*np.cos(2*np.pi*f[index]*t+ph[index,channel]);old[:,channel]+=v
                    if index in INDICES:
                        j=INDICES.index(index)
                        v=amp[index,channel]*np.cos(related[:,j]+(ph[index,1]-ph[index,0])*channel)
                    new[:,channel]+=v
            for name,target in [('old_main',old),('new_main',new)]:
                errors[name]=max(errors[name],float(abs(audio[name][start:stop]-target).max()))
            for name,theta in [('q_free',free),('q_related',related)]:
                q=powers(theta,law).reshape(-1,48,4).mean(axis=1)
                errors[name]=max(errors[name],float(abs(q-archive[name][start//48:stop//48]).max()))
            for name,main,detail in [('static','old_main','static_detail'),('post','old_main','post_detail'),
                                    ('relation_q','old_main','related_detail'),('relation_full','new_main','related_detail')]:
                error=float(abs(audio[name][start:stop]-audio[main][start:stop]-audio[detail][start:stop]).max())
                errors['mix_identity']=max(errors['mix_identity'],error)
        assert max(errors['old_main'],errors['new_main'])<3e-8
        assert max(errors['q_free'],errors['q_related'])<1e-9 and errors['mix_identity']<6e-8
        # Direct FIR inner products at early, boundary and late points: no OA convolution reuse.
        points=[0,31,4000,47999,48000,143999,288000,575999,1151999]
        if row['seconds']==180:points += [60*48000,120*48000,179*48000+17003,frames-1]
        points=np.array([v for v in points if v<frames]);count=frames+profile['warmup_frames']
        static=np.zeros((len(points),2));post=np.zeros_like(static);related=np.zeros_like(static)
        free=2*np.pi*(points[:,None]/48000)*f[INDICES]+ph[INDICES,0]
        q0=powers(free,law);q1=powers(phases(model,motion,points/48000),law)
        for index,kernel in enumerate(profile['kernels']):
            key=seed ^ ((0x9E3779B97F4A7C15*(index+1))&((1<<64)-1))
            gaussian=np.random.Generator(np.random.PCG64(key ^ 0x794323AA)).standard_normal(count)
            taps=np.asarray(kernel['taps']);at=points+profile['warmup_frames']
            v=np.array([taps@gaussian[j-np.arange(len(taps))] for j in at])*kernel['gain']
            ratio=np.array([1.,kernel['right_over_left']]);static+=v[:,None]*ratio
            if index<2:post+=v[:,None]*ratio;related+=v[:,None]*ratio
            else:
                uniform=np.random.Generator(np.random.PCG64(key ^ 0x94D049BB133111EB)).random(count)
                normal=np.random.Generator(np.random.PCG64(key ^ 0xD1B54A32D192ED03)).standard_normal(count)
                probability=report['probabilities'][index-2]
                sparse=normal*(uniform<probability)/np.sqrt(probability)
                v=np.array([taps@sparse[j-np.arange(len(taps))] for j in at])*kernel['gain']
                post+=v[:,None]*np.sqrt(q0[:,index-2,None])*ratio
                related+=v[:,None]*np.sqrt(q1[:,index-2,None])*ratio
        fir_errors={name:float(abs(audio[name][points]-target).max()) for name,target in
                    [('static_detail',static),('post_detail',post),('related_detail',related)]}
        assert max(fir_errors.values())<1.5e-8
        times=(np.arange(row['seconds']*1000)+.5)/1000
        values=motion(times);stats,curves=phase_stats(values)
        output=a.out/f'phase_{seed}.npz';np.savez_compressed(output,values=values,curves=curves,lags_ms=np.arange(501))
        r['phase_observations'].append(dict(label=str(seed),file=output.name,sha256=sha(output),**stats))
        if row['seconds']==180:
            short=independent_nodes(model,seed,int(np.ceil(26*200))+5)
            short_motion=interpolate.make_interp_spline((np.arange(len(short))-2)/200,short,k=3,bc_type='natural')
            prefix=float(abs(short_motion(times[:24000])-values[:24000]).max());assert prefix<1e-10
            r['prefix24s_motion_error']=prefix
        r['checks'].append(dict(seed=seed,seconds=row['seconds'],recurrence_error=recur,
          full_main_q_mix_errors=errors,direct_FIR_point_errors=fir_errors,direct_FIR_points=points.tolist(),
          all_saved_samples_finite_unclipped=True))
        print(dict(stage='independent_audio_checked',seed=seed,seconds=row['seconds'],errors=errors),flush=True)
    center=np.asarray(model['coordinate_center'])
    for part in ['train','check']:
        path=a.workspace/f'baselines/idle_closure_evidence_v1/evidence/observe1/source_{part}.npz'
        with np.load(path) as data:z=data['phasors']
        z=z[24::48];w=np.column_stack((z[:,2]*z[:,1].conj()*z[:,0].conj(),z[:,0]**3*z[:,1].conj()**2))
        values=np.angle(w*np.exp(-1j*center))+center;stats,curves=phase_stats(values)
        output=a.out/f'phase_source_{part}.npz';np.savez_compressed(output,values=values,curves=curves,lags_ms=np.arange(501))
        r['phase_observations'].append(dict(label='source_'+part,file=output.name,sha256=sha(output),**stats))
    protected={}
    for name,count in [('C_files_sha256.json',612),('voice_files_sha256.json',67)]:
        rows=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs'/name);assert len(rows)==count
        for path,digest in rows.items():assert sha(repo/path)==digest
        protected[name]=count
    r.update(result='passed',input_report_sha256=sha(a.input/'report.json'),protected=protected,
      independent_recursion_and_all_main_q_samples=True,full_wave_longrun_seconds=180,
      direct_FIR_is_selected_points_not_all_convolution_samples=True,
      source_and_generated_all501coordinate_lags=True,hearing_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],checks=len(r['checks'])),flush=True)
