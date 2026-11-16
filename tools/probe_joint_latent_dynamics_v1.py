"""Verify explicit coupled dynamics on known laws, without source training or audio."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal,linalg
    from joint_latent_dynamics_v1.state import prepare,endpoints,interpolation_matrix,interpolate,stationary_lag
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},cases=[],errors={})
    def check(name,actual,expected):
        value=float(abs(np.asarray(actual)-np.asarray(expected)).max());r['errors'][name]=value
        if not np.isfinite(value) or value>2e-11:raise ValueError((name,value))
    try:
        for name in ('tools/probe_joint_latent_dynamics_v1.py','tools/joint_latent_dynamics_v1/__init__.py',
            'tools/joint_latent_dynamics_v1/state.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        radius,theta=.85,.37
        rotation=radius*np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
        candidates=dict(diagonal=np.diag([-.5,.2,.8]),rotation=rotation,
            coupled=np.array([[.5,.35,0],[-.1,.6,.2],[.05,-.2,.45]]),
            white=np.zeros((3,3)),slow_rotation=rotation*(.95/radius))
        packets={}
        for name,transition in candidates.items():
            law=prepare(transition);d=len(transition);identity=np.eye(d)
            check(name+'_stationary_Lyapunov',transition@transition.T+law['innovation_root']@law['innovation_root'].T,identity)
            noise=np.random.Generator(np.random.PCG64(275)).standard_normal((512,d))
            state=endpoints(law,noise)
            # Independent general state-space simulator verifies every state.
            inputs=np.vstack((noise[1:],np.zeros((1,d))))
            _,independent,_=signal.dlsim((transition,law['innovation_root'],identity,np.zeros((d,d)),1.),inputs,x0=noise[0])
            check(name+'_every_state',state,independent)
            for lag in (0,1,2,4,8):
                power=identity.copy()
                for _ in range(lag):power=transition@power
                check(name+'_lag'+str(lag),stationary_lag(law,lag),power)
            for f in (0.,.1,.25,.5,.9,1.):
                whitening,covariance=interpolation_matrix(law,f)
                independent=np.linalg.inv(linalg.sqrtm(covariance))
                check(name+'_whitening'+str(f),whitening,independent)
                check(name+'_interpolation_C0'+str(f),whitening@covariance@whitening.T,identity)
                check(name+'_interpolation_samples'+str(f),interpolate(law,state[:-1],state[1:],f),
                    ((1-f)*state[:-1]+f*state[1:])@independent.T)
            if name=='diagonal':
                rho=np.diag(transition);old=np.empty_like(state);old[0]=noise[0]
                for j in range(1,len(old)):old[j]=rho*old[j-1]+np.sqrt(1-rho*rho)*noise[j]
                check('old_diagonal_formula_equivalence',state,old)
            if name=='coupled':
                _,covariance=interpolation_matrix(law,.5)
                diagonal=1/np.sqrt(np.diag(covariance))
                bad=covariance*diagonal[:,None]*diagonal[None,:]
                assert abs(bad-identity).max()>.05
                r['independent_scalar_interpolation_error_on_coupled_law']=float(abs(bad-identity).max())
            # Full joint endpoint covariance is an independent oracle for the
            # interpolated cross-time law. C0 correction alone must not be
            # mistaken for an exact continuous-time stochastic process.
            endpoint_covariance=np.empty((4*d,4*d))
            for i in range(4):
                for j in range(4):
                    power=np.linalg.matrix_power(transition,abs(i-j))
                    endpoint_covariance[i*d:(i+1)*d,j*d:(j+1)*d]=power if i>=j else power.T
            for f in (0.,.25,.5,1.):
                wf,_=interpolation_matrix(law,f)
                for g in (0.,.5,1.):
                    wg,_=interpolation_matrix(law,g)
                    future=np.zeros((d,4*d));past=np.zeros((d,4*d))
                    future[:,2*d:3*d]=(1-f)*wf;future[:,3*d:]=f*wf
                    past[:,:d]=(1-g)*wg;past[:,d:2*d]=g*wg
                    expected=wf@(((1-f)*(1-g)+f*g)*(transition@transition)
                        +f*(1-g)*np.linalg.matrix_power(transition,3)+(1-f)*g*transition)@wg.T
                    check(name+'_cross_time_bridge_'+str(f)+'_'+str(g),
                        future@endpoint_covariance@past.T,expected)
            r['cases'].append(dict(name=name,states=d,maximum_singular_value=law['maximum_singular_value']))
            packets.update({name+'_'+k:v for k,v in law.items() if isinstance(v,np.ndarray)})
            packets[name+'_noise']=noise;packets[name+'_states']=state
        # Same C0 and same diagonal C1 as scalar AR, while preserving known rotation.
        baseline=np.diag(np.diag(rotation))
        check('rotation_same_diagonal_C1',np.diag(rotation),np.diag(baseline))
        r['rotation_scalar_baseline_full_lag1_error']=float(np.linalg.norm(rotation-baseline))
        r['rotation_coupled_full_lag1_error']=0.
        rejects=[]
        for name,value in (('unstable',np.eye(2)),('rectangular',np.zeros((2,3))),
            ('nonfinite',np.array([[np.nan]])),('complex',np.array([[.2j]])),('empty',np.empty((0,0)))):
            try:prepare(value)
            except ValueError:rejects.append(name)
            else:raise AssertionError('Invalid transition accepted: '+name)
        np.savez_compressed(a.out/'known_laws.npz',**packets)
        r.update(result='explicit_coupled_latent_laws_known_verified',verification_passed=True,
            invalid_transitions_rejected=rejects,maximum_error=max(r['errors'].values()),
            packet_sha256=sha(a.out/'known_laws.npz'),no_vehicle_profile_fit_or_audio_or_C_change=True,
            interpolation_is_variance_correct_linear_bridge_not_exact_continuous_process=True,
            new_C1_source_eligible_for_statistics=False,no_aliasing_or_naturalness_or_realtime_qualification=True)
        save(a.out/'report.json',r);print(r['result'],r['maximum_error'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
