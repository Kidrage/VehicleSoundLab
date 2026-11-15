"""Independent full controls, all32 exact outcomes and8 iterative supported fits."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_supported_v1.audit_oracle import metric,matrices,block_right
    from observer_frequency_v1.audit_oracle import matrices as old_matrices,metric as old_metric,frame_adjoint
    from observer_complete_v1.audit_oracle import full_frame
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    helpers=('tools/observer_supported_v1/audit_oracle.py','tools/observer_frequency_v1/audit_oracle.py','tools/observer_complete_v1/audit_oracle.py','tools/observer_frequency_v1/reduced_oracle.py')
    for j,n in enumerate(helpers):shutil.copy2(repo/n,a.out/f'executed_oracle_{j}.py')
    r=dict(result='running',controls=[],cases=[],material_read=False,maximum_errors={},maximum_absolute_errors={})
    def check(name,x,y,scale=1.,gate=2e-9):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,name
        err=float(np.max(abs(x-y)/scale));assert err<gate,(name,err)
        r['maximum_errors'][name]=max(err,r['maximum_errors'].get(name,0.))
        r['maximum_absolute_errors'][name]=max(float(np.max(abs(x-y))),r['maximum_absolute_errors'].get(name,0.))
    def vec(z):return np.r_[z.real.ravel(),z.imag.ravel()]
    def unvec(x,shape):return x[:x.size//2].reshape(shape)+1j*x[x.size//2:].reshape(shape)
    def map_matrix(blocks,M,H,C):
        size=M*H*C;P=np.zeros((2*size,2*size))
        for h in range(H):
            for c in range(C):
                ids=np.r_[(np.arange(M)*H+h)*C+c,size+(np.arange(M)*H+h)*C+c]
                P[np.ix_(ids,ids)]=blocks[h]
        return P
    def gap(A,b,R,x,data_rows,t):
        B,y=A[:data_rows],b[:data_rows];res=B@x-y;p=B.T@res;v=linalg.solve(R,p,assume_a='pos')
        primal=float(np.sum((A@x-b)**2));den=float(res@res+p@v)
        dual=-(t*t)*den-2*t*float(y@res)
        gap=float((1-t)**2*(res@res)+(x+t*v)@R@(x+t*v))
        assert abs(primal-dual-gap)<2e-8*max(1.,primal)
        return primal,dual,gap
    try:
        source=load(a.study/'report.json');assert source['result']=='observer_supported_known_measured'
        for n,d in source['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==d
        path=a.study/'metric_controls.npz';assert sha(path)==source['metric_controls_sha256']
        with np.load(path) as z:
            m=metric(z['audio'],64.);weighted=m['rows']*m['weights'][None,:,None]
            check('metric_weights',m['weights'],z['weights'],m['weights'])
            check('supported_rows',weighted,z['rows'])
            full=np.zeros((len(m['keep']),2049,2),complex);full[m['keep']]=z['test']*m['weights'][None,:,None]*m['amplitude']
            gradient=frame_adjoint(full,m['full_coverage'],len(z['audio']))
            check('supported_adjoint',gradient,z['gradient'])
            check('supported_coverage',m['time_coverage'],z['coverage'])
            check('constant_power',metric(np.ones_like(z['audio']),64.)['band_power'],z['constant_power'])
            for rotation in (np.array([[0.,1.],[1.,0.]]),np.array([[.6,.8],[-.8,.6]])):
                other=metric(z['audio']@rotation,64.);check('LR_weight_invariance',other['weights'],m['weights'],m['weights'])
            other=metric(z['audio']*3.7,64.);check('positive_scale',other['rows']*other['weights'][None,:,None],weighted)
        for c in source['controls']:
            if 'file' not in c:continue
            path=a.study/c['file'];assert sha(path)==c['sha256']
            with np.load(path) as z:
                m=metric(z['audio'],64.);rows=m['rows']*m['weights'][None,:,None]
                check('control_weights',m['weights'],z['weights'],m['weights']);check('control_rows',rows,z['rows'])
                full=np.zeros((len(m['keep']),2049,2),complex);full[m['keep']]=rows*m['weights'][None,:,None]*m['amplitude']
                check('control_normal',frame_adjoint(full,m['full_coverage'],len(z['audio'])),z['normal'],max(1.,abs(z['normal']).max()))
                check('control_power',m['band_power'],z['band_power'])
                if c['name'] in ('first','last'):
                    assert not np.any(rows) and np.linalg.norm(z['rhs'][:z['audio'].size])>0
                r['controls'].append(c['name'])
        with np.load(a.study/'stereo_controls.npz') as z:
            assert sha(a.study/'stereo_controls.npz')==source['stereo_controls_sha256']
            m=metric(z['audio'],64.);A,b,Phi,R,data_rows=matrices(z['positions'],z['orders'],z['scale'],z['audio'],m)
            check('stereo_system_forward',A@z['u'],z['forward'],max(1.,abs(z['forward']).max()))
            check('stereo_system_adjoint',A.T@z['v'],z['backward'],max(1.,abs(z['backward']).max()))
            blocks=block_right(z['positions'],z['orders'],z['scale'],m);check('stereo_blocks',blocks,z['right_matrix'],max(1.,abs(blocks).max()))
            P=map_matrix(blocks,len(z['positions']),len(z['orders']),2)
            check('stereo_right',P@z['p'],z['right_forward'],max(1.,abs(z['right_forward']).max()))
            check('stereo_right_transpose',P.T@z['g'],z['right_backward'],max(1.,abs(z['right_backward']).max()))
        for case in source['cases']:
            path=a.study/case['file'];assert sha(path)==case['sha256']
            with np.load(path) as z:
                m=metric(z['audio'],64.);_,_,oldweights,_,_=old_metric(z['audio'],64.)
                systems,Phi,D=old_matrices(z['positions'],z['orders'],z['scale'],z['audio'],oldweights,m['sigma'])
                A,b,Phi2,R,data_rows=matrices(z['positions'],z['orders'],z['scale'],z['audio'],m)
                systems['supported']=(A,b);check('explicit_wave_basis',Phi,Phi2)
                check('case_weights',m['weights'],z['weights'],m['weights']);check('case_power',m['band_power'],z['band_power'])
                assert np.array_equal(m['floor_active'],z['floor_active'])
                row=dict(label=case['label'],variants={},floor_active=m['floor_active'].tolist())
                size=len(z['positions'])*len(z['orders']);high_ids=np.r_[np.arange(len(z['positions']))*2+1,size+np.arange(len(z['positions']))*2+1]
                truth=vec(z['source_nodes']/z['scale'][None]);high=Phi[:,high_ids]@truth[high_ids]
                def describe(x):
                    return dict(wave_NRMSE=float(np.linalg.norm(Phi@x-z['audio'].ravel())/np.linalg.norm(z['audio'])),
                        high_component_NRMSE=float(np.linalg.norm(Phi[:,high_ids]@(x-truth)[high_ids])/np.linalg.norm(high)))
                for tag,(AA,bb) in systems.items():
                    exact=linalg.lstsq(AA,bb,lapack_driver='gelsd')[0]
                    x=vec(z[tag+'_nodes']/z['scale'][None]);check('dense_solution',x,exact,max(1.,abs(exact).max()),2e-7)
                    H=AA.T@AA;check('normal_matrix',H,z[tag+'_normal_matrix'],max(1.,abs(H).max()))
                    check('normal_rhs',AA.T@bb,z[tag+'_normal_rhs'],max(1.,abs(AA.T@bb).max()))
                    stats=describe(x);res=AA@x-bb;g=float(np.linalg.norm(AA.T@res)/max(np.linalg.norm(AA.T@bb),1e-24))
                    for k,v in stats.items():check('metric_'+k,v,case['variants'][tag][k])
                    check('objective',res@res,case['variants'][tag]['objective'],max(1.,res@res))
                    assert g<2e-7;row['variants'][tag]=stats
                x=vec(z['iterative_nodes']/z['scale'][None]);exact=vec(z['supported_nodes']/z['scale'][None])
                err=float(np.linalg.norm(x-exact)/np.linalg.norm(exact));info=case['variants']['iterative']
                check('iterative_dense_error',err,info['dense_relative_error'])
                stats=describe(x)
                for k,v in stats.items():check('iterative_'+k,v,info[k])
                residual=A@x-b;g=float(np.linalg.norm(A.T@residual)/np.linalg.norm(A.T@b))
                assert info['converged']==bool(info['stop'] in (1,2,4,5) and g<2e-7)
                check('iterative_gradient',g,info['relative_stationarity'])
                for tag,xx in (('dense',exact),('iterative',x)):
                    cert=case[tag+'_certificate'];primal,dual,gg=gap(A,b,R,xx,data_rows,cert['residual_dual_scale'])
                    for k,v in dict(primal=primal,dual_lower_bound=dual,gap_upper_bound=gg).items():check('gap_'+k,v,cert[k],max(1.,abs(v)),2e-8)
                    assert bool(gg<=1e-6*primal+1e-10)==cert['additional_gap_gate_passed']
                blocks=block_right(z['positions'],z['orders'],z['scale'],m)
                P=map_matrix(blocks,len(z['positions']),len(z['orders']),1)
                check('right_blocks',blocks,z['right_matrix'],max(1.,abs(blocks).max()))
                check('right_full',P,z['right'],max(1.,abs(P).max()))
                condition=float(np.linalg.cond(A@P));check('condition',condition,case['preconditioned_dense_condition'],condition,2e-7)
                fitted=Phi[:,high_ids]@exact[high_ids];diff=fitted-high
                regions=[slice(0,544),slice(544,-544),slice(-544,None)]
                row['high_component_region_NRMSE']=[float(np.linalg.norm(diff[s])/np.linalg.norm(high[s])) for s in regions]
                bias=linalg.solve(A.T@A,-R@truth,assume_a='pos')
                check('analytic_regularization_bias',exact-truth,bias,max(1.,abs(truth).max()),2e-7)
                row['normalized_high_node_errors']=abs((z['supported_nodes']-z['source_nodes'])[:,1,0]/z['scale'][1,0]).tolist()
                row['fidelity_qualified']=row['variants']['supported']['high_component_NRMSE']<.02
                row['solver_qualified']=bool(info['converged'] and err<2e-7 and case['iterative_certificate']['additional_gap_gate_passed'] and condition<1e6)
                assert row['fidelity_qualified']==case['fidelity_qualified'] and row['solver_qualified']==case['solver_qualified']
                r['cases'].append(row);print('AUDITED SUPPORTED',case['label'],row['fidelity_qualified'],row['solver_qualified'],flush=True)
        assert len(r['cases'])==8
        r.update(result='independent_observer_supported_known_passed',all_fidelity_qualified=all(c['fidelity_qualified'] for c in r['cases']),
            all_solver_qualified=all(c['solver_qualified'] for c in r['cases']),producer_sha256=sha(a.study/'report.json'),
            auditor_sha256=sha(__file__),oracles_sha256={n:sha(repo/n) for n in helpers})
        save(a.out/'report.json',r);print(r['result'],r['all_fidelity_qualified'],r['all_solver_qualified'],flush=True)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
