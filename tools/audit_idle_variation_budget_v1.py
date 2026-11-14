"""Independent native phase, weighted QR and signed temporal bus-budget audit."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal,interpolate,linalg,fft
from research_archive_v1 import load,save,sha
from idle_conditioned_detail_v1.features import phases as original_phases
from idle_phase_recipe_v1.phase import spline as original_spline,phasors as original_phasors

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
run=load(a.input/'report.json');assert run['result']=='actual_idle_bus_variation_observed_pending_audit'
r=dict(result='running',input_sha256=sha(a.input/'report.json'),cases=[],errors={},QR_factorizations=0)
S=np.array([1,2,4]);starts=np.arange(12000,122401,960);nwindow=9600
w=np.hanning(nwindow+1)[:-1];sqrtw=np.sqrt(w)


def check(key,x,y,absolute=1e-10,relative=0.):
    x=np.asarray(x);y=np.asarray(y);d=float(np.max(np.abs(x-y)))
    r['errors'][key]=max(r['errors'].get(key,0.),d)
    assert d<=absolute+relative*float(np.max(np.abs(y))),(key,d)


def measured(audio,freq):
    multiplier=np.zeros(len(audio));multiplier[0]=multiplier[len(audio)//2]=1;multiplier[1:len(audio)//2]=2
    values=[]
    for hz in freq[S]:
        sos=signal.iirfilter(4,[hz-10,hz+10],btype='bandpass',ftype='butter',fs=48000,output='sos')
        filtered=signal.sosfiltfilt(sos,audio);analytic=fft.ifft(fft.fft(filtered)*multiplier)
        old_analytic=np.fft.ifft(np.fft.fft(filtered)*multiplier)
        phase_difference=abs(old_analytic/abs(old_analytic)-analytic/abs(analytic));index=int(np.argmax(phase_difference))
        candidate=dict(maximum_phase_difference=float(phase_difference[index]),frequency_hz=float(hz),sample=index,
            analytic_amplitude_at_maximum=float(abs(analytic[index])),
            maximum_complex_analytic_difference=float(abs(old_analytic-analytic).max()))
        if candidate['maximum_phase_difference']>r.get('old_numpy_FFT_comparison',{}).get('maximum_phase_difference',-1):
            r['old_numpy_FFT_comparison']=candidate
        values.append(analytic/abs(analytic))
    z=np.column_stack(values);check('all_native_measured_phasors',z,original_phases(audio,freq[S]),1e-11)
    return z


def observe(audio,freq,z):
    t=np.arange(len(audio))/48000;A=np.ones((len(audio),27))
    for k,hz in enumerate(freq):
        carrier=z[:,list(S).index(k)] if k in S else np.exp(2j*np.pi*hz*t)
        A[:,k]=carrier.real;A[:,k+13]=carrier.imag
    coefficients=[];conditions=[]
    for start in starts:
        design=A[start:start+nwindow]*sqrtw[:,None];Q,R=np.linalg.qr(design,mode='reduced')
        b=linalg.solve_triangular(R,Q.T@(audio[start:start+nwindow]*sqrtw[:,None]))
        coefficients.append((b[:13]-1j*b[13:26]).T);conditions.append(np.linalg.cond(R));r['QR_factorizations']+=1
    return np.array(coefficients),np.array(conditions)


def vector(c,ref):
    real=np.empty((len(c),6));z=c/ref
    real[:,:3]=z.real;real[:,3:]=z.imag
    return real


def cov(x,y):
    x=x-x.mean(axis=0);y=y-y.mean(axis=0);result=[]
    for lag in range(-25,26):
        indices=np.arange(max(0,-lag),min(len(x),len(x)-lag))
        result.append(np.einsum('ti,tj->ij',x[indices],y[indices+lag])/len(indices))
    return np.array(result)


def powers(v):
    v=v-v.mean(axis=0);frequency,density=signal.periodogram(v,fs=50,window=np.hanning(len(v)+1)[:-1],
        detrend=False,axis=0,scaling='density')
    psd=density*50/len(v)
    return np.array([psd[(frequency>=lo)&(frequency<hi)].sum(axis=0) for lo,hi in [[0,1],[1,3],[3,8],[8,25.000001]]]),psd


def verify_stats(c,ref,f,stats):
    series=[vector(c[:,j,S],ref) for j in range(c.shape[1])]
    total=cov(series[0],series[0]);variance=np.diag(total[25]);std=np.sqrt(variance)
    check('all_covariances',total,f['covariance'],1e-9)
    check('all_standard_deviations',std,f['std'],1e-9)
    rho=np.array([np.diag(total[25+lag])/variance for lag in [5,10,25]])
    check('all_rhos',rho,f['rho_100_200_500ms'],1e-8,2e-7)
    power,psd=powers(series[0]);check('all_temporal_PSD',psd,f['temporal_psd'],1e-10)
    check('all_temporal_bands',power,f['temporal_power'],1e-10)
    check('all_means',c[:,0,S].mean(axis=0),f['coefficient_mean'],1e-10)
    logstd=np.std(np.log(abs(c[:,0,S])),axis=0);check('all_log_std',logstd,f['log_std'],1e-9)
    for key,value in [('std',std),('rho_100_200_500ms',rho),('log_std',logstd),('temporal_power',power),('normalized_mean',series[0].mean(axis=0))]:
        check('all_report_metrics',value,stats[key],1e-8,2e-7)
    if len(series)==3:
        main=cov(series[1],series[1]);detail=cov(series[2],series[2])
        md=cov(series[1],series[2]);dm=cov(series[2],series[1]);cross=md+dm
        for key,value in [('main_covariance',main),('detail_covariance',detail),('main_detail_covariance',md),('detail_main_covariance',dm),('cross_covariance',cross)]:
            check('all_signed_bus_covariances',value,f[key],1e-9)
        check('all_signed_budget_identities',total,main+detail+cross,1e-9)
        ratio=np.array([np.diag(value[25])/variance for value in [main,detail,cross]])
        check('all_signed_variance_ratios',ratio,f['lag0_signed_variance_ratios'],1e-7,2e-7)
        check('all_main_std',np.sqrt(np.diag(main[25])),f['main_std'],1e-9)
        check('all_detail_std',np.sqrt(np.diag(detail[25])),f['detail_std'],1e-9)
        check('all_coefficient_sum_identities',c[:,0],c[:,1]+c[:,2],1e-10)


try:
    for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    for path,digest in run['inputs'].items():assert sha(path)==digest
    with np.load(a.input/'known_budget.npz') as f:
        main=f['main'];detail=f['detail'];mix=f['mix'];check('known_signed_mix',mix,main+detail,0)
        for key,left,right in [('total_covariance',mix,mix),('main_covariance',main,main),('detail_covariance',detail,detail)]:
            check('known_signed_covariances',cov(left,right),f[key],1e-12)
        check('known_negative_cross',cov(main,detail)+cov(detail,main),f['cross_covariance'],1e-12)
        power,psd=powers(mix);check('known_temporal_PSD',psd,f['temporal_psd'],1e-12)
        check('known_temporal_bands',power,f['temporal_power'],1e-12)
        assert np.all(np.diag(f['cross_covariance'][25])<0)
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    freq=np.array(profile['modal']['frequencies_hz'])
    new=load(a.workspace/'baselines/idle_local_partition_v1/evidence/compile2/model.json')
    phase_root=a.workspace/'baselines/idle_phase_recipe_v1/evidence/render2';phase_model=load(phase_root/'model.json')
    motions={};original_motions={};reference_cache={};last_paths=None;wave_cache={}
    for row in run['cases']:
        file=a.input/row['file'];assert sha(file)==row['sha256']
        with np.load(file) as archive:f={k:archive[k] for k in archive.files}
        metadata=row['metadata'];kind=metadata['kind'];current_freq=freq
        if kind=='known':
            root=a.workspace/'baselines/joint_osc_forward_v1/evidence/run2';spec=load(root/'spec.json');current_freq=np.array(spec['frequencies'])
            with np.load(root/'joint_AM_149921.npz') as n:mix=n['audio'][:144000]
            with np.load(root/'phase_only_149921.npz') as n:main=n['audio'][:144000]
            with np.load(root/'stream_149921.npz') as n:z=n['phasors'][:144000]
            audio=np.column_stack((mix,main,mix-main));ref=np.array(spec['amplitude'])[S]
        elif kind in ['source','samePSD_control']:
            path=Path(metadata['input_file'])
            with np.load(path) as n:audio=n['original_audio'][:,0,None];z=n['phasors']
            family=row['label'].rsplit('_',1)[0];train=path.with_name(family+'_train.npz')
            with np.load(train) as n:b=n['global_coefficients'][:,0]
            ref=(b[:13]-1j*b[13:26])[S]
        else:
            paths=(metadata['mix_file'],metadata['main_file'])
            if paths!=last_paths:
                wave_cache={}
                for name,path in zip(['mix','main'],paths):
                    value,rate=sf.read(path,always_2d=True);assert rate==48000;wave_cache[name]=value[:,0]
                last_paths=paths
            first=metadata['first_frame'];mix=wave_cache['mix'][first:first+144000];main=wave_cache['main'][first:first+144000]
            audio=np.column_stack((mix,main,mix-main))
            ref=np.array(profile['modal']['amplitude_LR'])[S,0] if metadata['condition']=='0.0' else np.array(new['main_amplitude_LR'])[:,0]
            if metadata['phase_basis']=='measured_acoustic':z=measured(mix,freq)
            else:
                seed=metadata['seed']
                if seed not in motions:
                    with np.load(metadata['motion_file']) as n:coords=n['coordinate_nodes']
                    motions[seed]=interpolate.make_interp_spline((np.arange(len(coords))-2)/200,coords,bc_type='natural')
                    original_motions[seed]=original_spline(phase_model,coords)
                t=np.arange(first,first+144000)/48000;motion=motions[seed](t)
                right=np.array([[-10.,8.],[-15.,-7.],[13.,1.]])/38
                phi=phase_model['carrier_phase_rad']+2*np.pi*phase_model['carrier_hz']*t
                z=np.exp(1j*(phi[:,None]*[2.,3.,5.]+motion@right.T))
                check('all_native_procedural_phasors',z,original_phasors(phase_model,original_motions[seed],t),1e-10)
        check('all_fixed_references',ref,f['reference'],0)
        c,condition=observe(audio,current_freq,z)
        check('all_weighted_QR_coefficients_FS',c,f['coefficients'],1e-9)
        if 'design_condition' in f:check('all_basis_conditions',condition,f['design_condition'],1e-7,1e-8)
        verify_stats(c,ref,f,row['stats'])
        r['cases'].append(dict(label=row['label'],windows=116,buses=audio.shape[1]))
        if len(r['cases'])%17==0:save(a.out/'report.json',r);print(dict(audited=len(r['cases']),total=153),flush=True)
    assert len(r['cases'])==153 and r['QR_factorizations']==17748
    r.update(result='passed',all153cases_QR_native_phase_and_signed_temporal_budgets=True,
        source_main_detail_physical_separation_claimed=False,new_audio_or_model=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],QR_factorizations=r['QR_factorizations'],errors=r['errors']),flush=True)
