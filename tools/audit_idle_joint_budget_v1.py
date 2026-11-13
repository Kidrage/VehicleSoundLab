"""Independent fourth-tensor contractions, ensemble sums, SVD and dual checks."""
import argparse,itertools,math,shutil,sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','certificate','out']:
    p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha

PAIRS=[(i,j) for i in range(4) for j in range(i,4)]


def total(x):return math.fsum(np.asarray(x).tolist())


def mixed(x,w):
    mean=np.array([total(w*x[:,b]) for b in range(4)])
    y=x-mean
    second=np.array([[total(w*y[:,b]*y[:,c]) for c in range(4)] for b in range(4)])
    v=second.diagonal()
    return np.array([[total(w*y[:,b]**2*y[:,c]**2)-v[b]*v[c]-2*second[b,c]**2 for c in range(4)] for b in range(4)])


def tensor_operator(h,d):
    # Sum all nonzero T_ijkl permutations, independently of the compact three-term map.
    result=np.zeros((10,10))
    for col,(i,j) in enumerate(PAIRS):
        entries=[(i,i,i,i)] if i==j else sorted(set(itertools.permutations([i,i,j,j])))
        for row,(b,c) in enumerate(PAIRS):
            result[row,col]=math.fsum(total(h[b,ii]*h[b,jj]*h[c,kk]*h[c,ll])*(d if i==j else 1)
                for ii,jj,kk,ll in entries)
    return result


def pack(x):return np.array([x[i,j] for i,j in PAIRS])


def audit_solve(A,target,row_scale,solution):
    scaled=A/row_scale[:,None]
    columns=np.sqrt(np.array([total(scaled[:,j]**2) for j in range(10)]))
    normalized=scaled/columns
    U,s,Vh=np.linalg.svd(normalized,full_matrices=False)
    cutoff=np.finfo(float).eps*10*s[0]
    rank=int(np.sum(s>cutoff))
    assert rank==solution['rank']
    if rank<10:
        assert solution['status']=='rank_deficient_UNKNOWN'
        return 0.
    value=(Vh.T@((U.T@(target/row_scale))/s))/columns
    actual=pack(np.array(solution['latent']))
    error=float(np.linalg.norm(value-actual)/max(1.,np.linalg.norm(actual)))
    assert error<1e-8,error
    latent=np.array(solution['latent'])
    assert np.allclose(A@actual,solution['prediction'],rtol=1e-10,atol=1e-20)
    eigen=np.linalg.eigvalsh(latent)
    assert np.allclose(eigen,solution['eigenvalues'],rtol=1e-9,atol=1e-10)
    if solution['status']=='latent_indefinite_REJECTED':
        assert eigen[0]<-solution['numeric_margin']
    elif solution['status']=='nonnegative_factor_CERTIFIED':
        W=np.array(solution['factor'])
        assert np.min(W)>=0 and np.allclose(W@W.T,latent,atol=1e-10)
        maximum=max(total(row) for row in W)
        bound=1/maximum**2
        expected=bound/(1+bound) if solution['existence_parameter']=='common_Bernoulli_p' else bound
        assert abs(expected-solution['existence_upper_bound'])<1e-12
    else:raise AssertionError(solution['status'])
    return error


def audit_certificate(A,scale,target,latent,row):
    v=np.array(row['vector']);u=np.array(row['dual'])
    assert abs(v@v-1)<1e-12
    g=np.array([v[i]*v[j]*(1 if i==j else 2) for i,j in PAIRS])
    assert np.linalg.norm(u@(A/scale[:,None])-g)<1e-10
    value=total(u*target/scale)
    rayleigh=total(v*(latent@v))
    assert value<0 and abs(value-rayleigh)<1e-8*max(1.,abs(value))
    assert np.isclose(value,row['value'],atol=1e-10,rtol=1e-10)
    assert np.isclose(rayleigh,np.linalg.eigvalsh(latent)[0],rtol=1e-10,atol=1e-10)
    bound=-value/math.sqrt(total(u*u))
    assert np.isclose(bound,row['minimum_required_normalized10_moment_change'],atol=1e-12)


a.out.mkdir(parents=True,exist_ok=False)
shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running')
try:
    observed=load(a.input/'report.json');cert=load(a.certificate/'report.json')
    assert observed['result']=='both_joint_budget_families_examined_NO_sound_promotion'
    assert cert['input_report_sha256']==sha(a.input/'report.json')
    for name,digest in observed['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    assert sha(repo/'tools/certify_idle_joint_budget_v1.py')==sha(a.certificate/'executed_certificate.py')
    assert cert['plan_sha256']==sha(repo/'research/idle_joint_budget_certificate_v1_plan.json')==sha(a.certificate/'executed_plan.json')
    parent=a.workspace/'baselines/idle_joint_cumulant_v1'
    assert sha(parent/'manifest.json')==observed['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in observed['inputs'].items():assert sha(parent/name)==digest==table[name]
    with np.load(a.input/'known/Gaussian_FIR.npz') as archive:
        known={key:archive[key] for key in archive.files}
    q,w,h=known['q'],known['q_weights'],known['h']
    expected_audio=(q@h[:,:,0].T)[:,None,:]+(q@h[:,:,1].T)[None,:,:]
    assert np.array_equal(expected_audio.reshape(-1,4),known['audio'])
    assert np.array_equal((w[:,None]*w[None,:]).ravel(),known['weights'])
    # Rebuild all original mark/three-point samples rather than trust their moments.
    for index in range(162):
        mark=index//81;number=index%81
        digits=[(number//3**(3-b))%3 for b in range(4)]
        sample=[mark*2*math.sqrt(3.)*(digit-1) for digit in digits]
        weight=(.25 if mark else .75)*math.prod(2/3 if d==1 else 1/6 for d in digits)
        assert np.allclose(q[index],sample,atol=1e-15) and abs(w[index]-weight)<1e-15
    actual=mixed(known['audio'],known['weights'])
    A=tensor_operator(h,3)
    assert np.allclose(pack(actual),A@np.full(10,3.),atol=1e-10)
    maximum_ensemble_error=float(abs(actual-observed['known']['Gaussian_FIR']['observation']['cumulant']).max())
    with np.load(a.input/'known/Poisson_binomial.npz') as archive:
        known={key:archive[key] for key in archive.files}
    amplitude=known['amplitude'];rate=float(known['rate']);position=0
    for count in range(13):
        probability=math.exp(-rate)*rate**count/math.factorial(count)
        for negatives in itertools.product(range(count+1),repeat=4):
            expected=amplitude*np.array([count-2*k for k in negatives])
            expected_w=probability*math.prod(math.comb(count,k)/2**count for k in negatives)
            assert np.array_equal(known['audio'][position],expected)
            assert abs(known['weights'][position]-expected_w)<1e-16
            position+=1
    assert position==len(known['audio'])
    actual=mixed(known['audio'],known['weights'])
    assert np.allclose(actual,rate*np.outer(amplitude**2,amplitude**2),atol=1e-11)
    maximum_ensemble_error=max(maximum_ensemble_error,float(abs(actual-observed['known']['Poisson_binomial']['observation']['cumulant']).max()))
    maximum_solve_error=0.
    for case in observed['known']['inverse_controls']:
        control_h=np.tile(h[:1],(4,1,1)) if case['name']=='rank_deficient' else h
        expected_A=tensor_operator(control_h,3 if case['family']=='variance_factors' else 1)
        assert np.allclose(expected_A,case['A'],rtol=1e-12,atol=1e-12)
        if case['name']!='rank_deficient':
            W=np.array([[1.,0,0,0],[.2,.9,0,0],[.1,.15,.8,0],[.05,.1,.2,.7]])
            expected_C=W@W.T if case['name']=='positive' else np.eye(4)
            if case['name']=='indefinite':expected_C[0,1]=expected_C[1,0]=2.
            assert np.allclose(expected_A@pack(expected_C),case['target'],atol=1e-12)
        maximum_solve_error=max(maximum_solve_error,audit_solve(np.array(case['A']),np.array(case['target']),np.ones(10),case['solution']))
        if case['name']=='indefinite':
            row=next(v['certificate'] for v in cert['known'] if v['family']==case['family'])
            audit_certificate(np.array(case['A']),np.ones(10),np.array(case['target']),np.array(case['solution']['latent']),row)
    print(dict(stage='all_known_ensembles_and_inverse_controls_verified'),flush=True)
    source=load(parent/'evidence/observe1/report.json')
    architecture=np.load(parent/'evidence/observe1/architecture.npz')
    variance=architecture['variance'];outer=np.outer(variance,variance);main=architecture['main_cumulant']
    train=np.array(next(v for v in source['observations'] if v['label']=='training')['raw']['normalized'])
    check=np.array(next(v for v in source['observations'] if v['label']=='check')['raw']['normalized'])
    maximum_operator_error=0.
    for family,row in observed['families'].items():
        z=np.load(a.input/(family+'_budget.npz'))
        assert np.array_equal(z['h'],architecture['responses'][:,2:6,:])
        assert np.array_equal(z['variance'],variance) and np.array_equal(z['main'],main)
        assert np.array_equal(z['target'],pack(train*outer-main))
        assert np.array_equal(z['row_scale'],pack(outer))
        A=tensor_operator(z['h'],row['multiplier'])
        error=float(abs((A-z['A'])/z['row_scale'][:,None]).max())
        maximum_operator_error=max(maximum_operator_error,error)
        assert error<1e-12
        solution=load(a.input/(family+'_train.json'))
        assert sha(a.input/(family+'_train.json'))==row['train_solution_sha256'] and solution==row['solution']
        maximum_solve_error=max(maximum_solve_error,audit_solve(A,z['target'],z['row_scale'],solution))
        prediction=(np.array([[solution['prediction'][PAIRS.index((min(b,c),max(b,c)))] for c in range(4)] for b in range(4)])+main)/outer
        assert np.allclose(prediction,row['check']['prediction'],atol=1e-10)
        assert np.allclose(row['check']['new_error'],prediction-check,atol=1e-10)
        old=np.array(source['theoretical_raw']['1'])
        assert np.allclose(row['check']['old_independent'],old,atol=1e-12)
        assert np.allclose(row['check']['old_error'],old-check,atol=1e-12)
        assert abs(row['check']['error_norm']-np.linalg.norm(prediction-check))<1e-10
        assert abs(row['check']['old_error_norm']-np.linalg.norm(old-check))<1e-10
        assert not row['check']['generative_certificate']
        audit_certificate(A,z['row_scale'],z['target'],np.array(solution['latent']),cert['families'][family])
        u=np.array(cert['families'][family]['dual'])
        check_value=total(u*pack(check*outer-main)/z['row_scale'])
        assert np.isclose(check_value,cert['families'][family]['check_value_without_new_fit'],rtol=1e-10,atol=1e-10)
        assert cert['families'][family]['same_training_hyperplane_check_violates']==bool(check_value<0)
        assert np.isclose(cert['families'][family]['check_lower_bound_with_same_hyperplane'],
            max(0.,-check_value)/math.sqrt(total(u*u)),rtol=1e-10,atol=1e-12)
        print(dict(family=family,full_tensor_operator_verified=True,linear_relaxation_status=solution['status']),flush=True)
    r.update(result='both_budget_families_known_controls_tensor_maps_and_certificates_verified',
        known_ensembles=2,known_inverse_controls=6,real_families=2,separation_certificates=4,
        maximum_ensemble_error=maximum_ensemble_error,maximum_normalized_operator_error=maximum_operator_error,
        maximum_relative_SVD_solution_error=maximum_solve_error,
        input_report_sha256=sha(a.input/'report.json'),certificate_report_sha256=sha(a.certificate/'report.json'),
        no_sound_or_RPM_source_qualification=True)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
