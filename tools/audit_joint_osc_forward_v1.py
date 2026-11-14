"""Independent direct FIR, QR projection, recovered parameters and Gaussian quadrature."""
import argparse,csv,math,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import linalg,signal
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',QR_windows=0,real_engine_source_identified=False)
errors={key:0. for key in ['all_covariance','all_native_covariance','all_nodes','all_latent','all_gains','all_waveforms',
    'all_QR_coefficients','all_summary_metrics','all_quadrature_moments','all_finite_power','all_trace_costs','all_Jacobians']}
select=np.array([1,2,4]);starts=np.arange(12000,122401,960);weight=np.sin(np.pi*np.arange(9600)/9600)**2;sqrtw=np.sqrt(weight)
def update(key,value):errors[key]=max(errors[key],float(value))
def part_QR(audio,frequencies,z,base=None):
    if audio.ndim==1:audio=audio[:,None]
    t=np.arange(144000)/48000;c=np.cos(2*np.pi*t[:,None]*frequencies);s=np.sin(2*np.pi*t[:,None]*frequencies)
    c[:,select]=z.real;s[:,select]=z.imag;design=np.column_stack((c,s,np.ones(144000)))
    values=[];responses=[];constant=[]
    for first in starts:
        Q,R=linalg.qr(design[first:first+9600]*sqrtw[:,None],mode='economic')
        beta=linalg.solve_triangular(R,Q.T@(audio[first:first+9600]*sqrtw[:,None]))
        values.append(beta[:13]-1j*beta[13:26]);r['QR_windows']+=1
        if base is not None:
            inverse=linalg.solve_triangular(R,np.eye(27));rows=inverse[select]-1j*inverse[select+13]
            kernel=(rows@Q.T)*sqrtw
            responses.append(kernel[:,:,None]*z[first:first+9600].real[None,:,:]*amplitude[select])
            constant.append(kernel@base[first:first+9600])
    return np.array(values),((np.array(responses),np.array(constant)) if base is not None else None)

def response(cache,g):
    kernels,base=cache;v=np.array([g[first:first+9600] for first in starts])
    return base+np.einsum('wjtm,wtm->wj',kernels,v,optimize=True)

def native_gain(latent,parameters,enabled=True):
    s=np.array([.12,.10,.09]);v=np.zeros((len(latent),3));der=np.zeros((2,len(latent),3))
    if enabled:
        q=np.asarray(parameters)
        v[:,0]=s[0]*(q[0]*latent[:,0]+np.sqrt(1-q[0]**2)*latent[:,2])-s[0]**2
        v[:,1]=s[1]*(q[1]*latent[:,1]+np.sqrt(1-q[1]**2)*latent[:,3])-s[1]**2
        v[:,2]=s[2]*latent[:,4]-s[2]**2
        der[0,:,0]=s[0]*(latent[:,0]-q[0]/np.sqrt(1-q[0]**2)*latent[:,2])
        der[1,:,1]=s[1]*(latent[:,1]-q[1]/np.sqrt(1-q[1]**2)*latent[:,3])
    g=np.exp(v);return g,der*g[None,:,:],v

def geometric(x,n):return n*np.sinc(n*x)/np.sinc(x)*np.exp(1j*np.pi*(n-1)*x)
def hann_transform(f,n):
    x=np.asarray(f)/48000
    return (.5*geometric(x,n)-.25*geometric(x+1/n,n)-.25*geometric(x-1/n,n))/(n/2)

try:
    source=load(a.input/'report.json');assert source['result']=='known_joint_forward_inverse_and_moments_pending_audit'
    r['input_sha256']=sha(a.input/'report.json')
    for path,digest in source['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    spec=load(a.input/'spec.json');frequencies=np.array(spec['frequencies']);amplitude=np.array(spec['amplitude']);initial=np.array(spec['initial'])
    assert len(frequencies)==13 and np.array_equal(frequencies[select],[75,112.5,187.5])
    M=np.array([[-1.,-1.,1.],[3.,-2.,0.]]);right=linalg.lstsq(M,np.eye(2))[0]
    phase_map=np.zeros((13,5));phase_map[select,:2]=right*[.18,.22]
    assert abs(phase_map-spec['phase_map']).max()<1e-14
    with np.load(a.input/'kernels.npz') as f:kernel={key:f[key] for key in f.files}
    taps=kernel['taps'];h=np.exp(-.5*((np.arange(64)-31.5)/8)**2);h/=np.linalg.norm(h)
    factor=np.eye(5);factor[1,:2]=[.35,np.sqrt(1-.35**2)]
    assert abs(taps-h[:,None,None]*factor).max()<1e-14
    tables={}
    for name,H in [('main',taps),('delayed',kernel['delayed_taps'])]:
        C=np.array([sum(H[j]@H[j+k].T for j in range(len(H)-k)) for k in range(4)])
        update('all_covariance',abs(C[0]-kernel[name+'_covariance']).max())
        block=np.block([[C[j-i] if j>=i else C[i-j].T for j in range(4)] for i in range(4)])
        table=kernel[name+'_transform'];W=kernel[name+'_weights'];raw=[]
        for fraction in range(240):
            B=np.hstack([np.eye(5)*v for v in W[fraction]]);R=B@block@B.T;raw.append(R)
            update('all_native_covariance',abs(table[fraction]@R@table[fraction].T-C[0]).max())
        assert abs(np.array(raw)-kernel[name+'_raw_covariance']).max()<1e-12
        tables[name]=(W,table,C[0])
    W,T,C0=tables['main'];assert abs(C0-factor@factor.T).max()<1e-12
    truth=np.array([.65,-.55]);fitted=np.array(source['fit']['parameters']);assert abs(fitted-truth).max()<1e-6
    fit_cache=None;fit_latent=None;fit_target=None
    for stream in source['streams']:
        seed=stream['seed'];assert sha(a.input/stream['file'])==stream['sha256']
        with np.load(a.input/stream['file']) as f:Z=f['latent'];node=f['nodes'];white=f['white'];savedz=f['phasors'];savedbase=f['base']
        expected=np.array([sum(taps[j]@white[i+len(taps)-1-j] for j in range(len(taps))) for i in range(len(node))])
        update('all_nodes',abs(expected-node).max())
        idx=np.arange(len(Z));k=idx//240;fraction=idx%240
        raw=sum(W[fraction,j,None]*expected[k+j+1] for j in range(4));latent=np.einsum('fij,fj->fi',T[fraction],raw)
        update('all_latent',abs(latent-Z).max())
        theta=2*np.pi*np.arange(len(Z))[:,None]/48000*frequencies+initial+latent@phase_map.T
        z=np.cos(theta[:,select])+1j*np.sin(theta[:,select]);update('all_waveforms',abs(z-savedz).max())
        mask=np.ones(13,bool);mask[select]=False;base=np.cos(theta[:,mask])@amplitude[mask]
        update('all_waveforms',abs(base-savedbase).max())
        cases=[row for row in source['cases'] if row['seed']==seed];saved=[];audios=[]
        for row in cases:
            assert sha(a.input/row['file'])==row['sha256']
            with np.load(a.input/row['file']) as f:contents={key:f[key] for key in f.files}
            kind=row['kind'];parameters=truth if kind=='joint_AM' else np.zeros(2);enabled=kind!='phase_only'
            g,_,log=native_gain(latent,parameters,enabled)
            x=base+np.sum(np.cos(theta[:,select])*g*amplitude[select],axis=1)
            update('all_gains',max(abs(g-contents['gain']).max(),abs(log-contents['loggain']).max()))
            update('all_waveforms',abs(x-contents['audio']).max());saved.append(contents);audios.append(x)
        for portion,part in enumerate(['train','check']):
            start=portion*144000;stop=start+144000
            calculated,cache=part_QR(np.column_stack(audios)[start:stop],frequencies,z[start:stop],base[start:stop] if seed==149921 and portion==0 else None)
            if cache is not None:fit_cache=cache;fit_latent=latent[:144000];fit_target=np.log(abs(saved[2]['train_true_coefficients'][:,select]))
            for j,(row,contents) in enumerate(zip(cases,saved)):
                update('all_QR_coefficients',abs(calculated[:,:,j]-contents[part+'_true_coefficients']).max())
                observed,_=part_QR(audios[j][start:stop],frequencies,contents[part+'_measured_phasors'])
                update('all_QR_coefficients',abs(observed[:,:,0]-contents[part+'_measured_coefficients']).max())
                std=np.std(np.log(abs(observed[:,select,0])),axis=0)
                phase=float(np.quantile(abs(np.angle(contents[part+'_measured_phasors'][12000:-12000]/z[start:stop][12000:-12000])),.95))
                entry=row['parts'][portion]
                update('all_summary_metrics',max(abs(std-entry['measured_log_std']).max(),abs(phase-entry['phase_error_p95_rad'])))
                noAM=row['kind']=='phase_only'
                if noAM:assert std.max()<=.003 and phase<=.05 and entry['no_AM_original_gate']
                gw=contents['gain'][start:stop];means=np.array([weight@gw[first:first+9600]/sum(weight) for first in starts])
                expmeans=np.exp(np.array([weight@np.log(gw[first:first+9600])/sum(weight) for first in starts]))
                update('all_gains',max(abs(means-contents[part+'_Hann_mean_gain']).max(),abs(expmeans-contents[part+'_exp_Hann_mean_loggain']).max()))
                for field,value in [('naive_Hann_gain_max_relative_error',abs(abs(calculated[:,select,j])/(amplitude[select]*means)-1).max()),
                    ('naive_exp_Hann_log_max_relative_error',abs(abs(calculated[:,select,j])/(amplitude[select]*expmeans)-1).max())]:update('all_summary_metrics',abs(value-entry[field]))
        print(dict(seed=seed,QR_windows=r['QR_windows'],maximum_QR_error=errors['all_QR_coefficients']),flush=True)
        # Full native predictions using fitted parameters, with supplied known inputs.
        g,_,_=native_gain(latent,fitted);prediction=base+np.sum(np.cos(theta[:,select])*g*amplitude[select],axis=1)
        joint=saved[2]['audio'];update('all_waveforms',abs(prediction-joint).max())
        assert abs(prediction-joint).max()<1e-7
    # Deterministic3s control.
    row=next(v for v in source['cases'] if v['kind']=='constant');assert sha(a.input/row['file'])==row['sha256']
    with np.load(a.input/row['file']) as f:constant={key:f[key] for key in f.files}
    theta=2*np.pi*np.arange(144000)[:,None]/48000*frequencies+initial
    x=np.cos(theta)@amplitude;z=np.exp(1j*theta[:,select])
    update('all_waveforms',abs(x-constant['audio']).max())
    q,_=part_QR(x,frequencies,z);update('all_QR_coefficients',abs(q[:,:,0]-constant['train_true_coefficients']).max())
    q,_=part_QR(x,frequencies,constant['train_measured_phasors']);update('all_QR_coefficients',abs(q[:,:,0]-constant['train_measured_coefficients']).max())
    assert np.std(np.log(abs(q[:,select,0])),axis=0).max()<=.003
    # All actual inverse evaluations and Jacobian controls via independently compiled QR response.
    def inverse_response(parameters):
        g,dg,_=native_gain(fit_latent,parameters);coefficient=response(fit_cache,g)
        dc=np.array([response(fit_cache,d)-fit_cache[1] for d in dg])
        return np.log(abs(coefficient)),np.moveaxis(np.real(dc/coefficient[None,:,:]),0,-1).reshape(-1,2)
    for entry in source['fit']['trace']:
        predicted,jac=inverse_response(entry['parameters']);residual=(predicted-fit_target).ravel()
        update('all_trace_costs',abs(float(residual@residual)-entry['squared_error']))
    for entry in source['jacobian_controls']:
        parameters=np.array(entry['parameters']);_,jac=inverse_response(parameters);numeric=[]
        for j in range(2):
            step=np.zeros(2);step[j]=1e-6
            numeric.append(((inverse_response(parameters+step)[0]-inverse_response(parameters-step)[0])/(2e-6)).ravel())
        error=abs(jac-np.column_stack(numeric)).max();assert error<1e-7
        update('all_Jacobians',float(error))
    final,jac=inverse_response(fitted);singular=np.linalg.svd(jac,compute_uv=False)
    assert abs(singular-source['fit']['Jacobian_singular_values']).max()<1e-10
    assert abs(final-fit_target).max()<1e-8 and singular[0]/singular[-1]<1000
    # Geometric Hann transform controls, then independent Gaussian quadrature matrices.
    for n in [80,81]:
        freq=np.array([0.,48000/n,-48000/n,.00001,75.31,112.73]);w=np.sin(np.pi*np.arange(n)/n)**2;w/=sum(w)
        explicit=np.array([np.dot(w,np.exp(2j*np.pi*value*np.arange(n)/48000)) for value in freq])
        assert abs(hann_transform(freq,n)-explicit).max()<1e-12
    from itertools import product
    gh,gw=np.polynomial.hermite.hermgauss(9);grid=np.array(list(product(range(9),repeat=5)))
    V=(np.sqrt(2)*gh[grid])@np.linalg.cholesky(C0).T;probability=np.prod(gw[grid]/np.sqrt(np.pi),axis=1)
    quadrature={}
    for kind,parameters,enabled in [('phase_only',[0,0],False),('independent_AM',[0,0],True),('joint_AM',[.65,-.55],True)]:
        g,_,_=native_gain(V,parameters,enabled);G=np.ones((len(V),13));G[:,select]=g
        y=G*np.exp(1j*(V@phase_map.T));first=probability@y
        same=y.T@(y*probability[:,None]);opposite=y.T@(y.conj()*probability[:,None]);quadrature[kind]=(first,same,opposite)
        assert abs(np.diag(opposite)-1).max()<1e-12
    quadrature['constant']=(np.ones(13),np.ones((13,13)),np.ones((13,13)))
    powers={row['case']:row for row in source['power']}
    for row in source['cases']:
        with np.load(a.input/row['file']) as f:
            first,same,opposite=quadrature[row['kind']]
            for part_index,part in enumerate(['train','check']):
                if part+'_expected_modal_second_moment' not in f:continue
                for key,value in [('theoretical_first',first),('theoretical_same',same),('theoretical_opposite',opposite)]:
                    update('all_quadrature_moments',abs(value-f[part+'_'+key]).max())
                fm=frequencies[:,None]+frequencies[None,:];fd=frequencies[:,None]-frequencies[None,:]
                pm=initial[:,None]+initial[None,:];pd=initial[:,None]-initial[None,:]
                start_time=part_index*3+.25
                plus=hann_transform(fm,120000)*np.exp(1j*(pm+2*np.pi*fm*start_time))
                minus=hann_transform(fd,120000)*np.exp(1j*(pd+2*np.pi*fd*start_time))
                matrix=.5*(same*plus+opposite*minus).real*amplitude[:,None]*amplitude[None,:]
                update('all_finite_power',abs(matrix-f[part+'_expected_modal_second_moment']).max())
                power=powers[str(row['seed'])+'_'+row['kind']+'_'+part]
                x=f['audio'][part_index*144000:(part_index+1)*144000];w=np.sin(np.pi*np.arange(120000)/120000)**2;w/=sum(w)
                realized=math.fsum(w*x[12000:-12000]**2)
                values={'expected_total':matrix.sum(),'expected_diagonal':np.trace(matrix),
                    'expected_signed_cross':matrix.sum()-np.trace(matrix),'realized':realized,'realized_over_expected':realized/matrix.sum()}
                for key,value in values.items():update('all_finite_power',abs(float(value)-power[key]))
    assert errors['all_Jacobians']<1e-7
    assert max(value for key,value in errors.items() if key!='all_Jacobians')<1e-9,errors
    ch=list(csv.reader((repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig')))
    assert len(ch)==620 and all(sha(repo/row[0])==row[4] for row in ch[1:])
    voices=load(a.workspace/'baselines/idle_microtexture_c_v1/inputs/voice_files_sha256.json')
    assert len(voices)==67 and all(sha(repo/path)==digest for path,digest in voices.items())
    r.update(result='passed',errors=errors,all3native_streams_and10waveforms=True,all19true_and19measured_portions_QR=True,
        all_inverse_trace_and_known_parameters_checked=True,all13x13Gaussian_moments_and_finite_power_checked=True,
        old619C_H_and67voices_exact=True,measured_noAM_original_gates_passed=source['measured_no_AM_gates_passed'],
        note='Known latent inputs supplied; implementation forward/inverse contract only, not real-engine hidden-source recovery or new listening evidence.')
except Exception as exc:r.update(result='failed',error=repr(exc),errors=errors);raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],QR_windows=r['QR_windows'],errors=errors),flush=True)
