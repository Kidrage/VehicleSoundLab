"""Independent dense feature-skew, scalar coefficient-power and native-time audit."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import math
    import numpy as np
    from scipy import linalg
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',errors={},cases=[])
    def check(name,actual,expected,scale=1.):
        actual,expected=np.asarray(actual),np.asarray(expected);assert actual.shape==expected.shape,name
        error=float(np.max(abs(actual-expected)))/max(float(scale),1e-300);r['errors'][name]=error
        if not np.isfinite(error) or error>2e-11:raise ValueError((name,error))
    def centered(x):return x-np.array([math.fsum(col)/len(x) for col in x.T])
    try:
        source=load(a.study/'report.json');assert source['result']=='saved_six_shared_feature_directions_traced_to_sources'
        repo=Path(__file__).resolve().parents[1]
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():assert sha(name)==digest
        assert len(source['known'])==4 and source['known'][-1]['dense_squared_norm']==0
        for known in source['known']:check('known_'+known['label'],known['pair_squared_norm'],known['dense_squared_norm'])
        for case in source['cases']:
            label=case['label'];meta=case['metadata'];path=a.study/label/'trace.npz';assert sha(path)==case['trace_sha256']
            with np.load(path) as f:data={k:f[k] for k in f.files}
            with np.load(case['source_training_path']) as f:pc=f['pc'];raw=f['source_rows'];coords=f['coordinates']
            with np.load(case['source_profile_path']) as f:b=f['basis']
            with np.load(case['source_packet']) as f:positions=f['positions']
            n,k=pc.shape;h=raw.shape[1]//4
            lengths=np.array([math.sqrt(math.fsum(v*v for v in col)) for col in b.T]);u=b/lengths
            check(label+'_lengths',data['column_lengths'],lengths)
            check(label+'_unit_basis',data['unit_basis'],u)
            check(label+'_orthogonality',np.einsum('di,dj->ij',u,u,optimize=False),np.eye(k))
            x=centered(pc)
            lag=np.array([[math.fsum(x[t+1,i]*x[t,j] for t in range(n-1))/(n-1) for j in range(k)] for i in range(k)])
            check(label+'_pc_lag_all',data['pc_lag1'],lag)
            shared=centered(np.einsum('nk,dk->nd',pc,b,optimize=False))
            cov=shared[1:].T@shared[:-1]/(n-1);skew=(cov-cov.T)/2
            dense_squared=float(np.linalg.norm(skew)**2)
            check(label+'_pair_total_dense_closure',sum(v['squared_feature_skew_norm'] for v in case['pairs']),dense_squared,dense_squared)
            values={(i,j):2*(lengths[i]*lengths[j]*(lag[i,j]-lag[j,i])/2)**2 for i in range(k) for j in range(i+1,k)}
            total=math.fsum(values.values());ordered=sorted(values,key=lambda ij:(-values[ij],ij))
            assert [(v['pc_i'],v['pc_j']) for v in case['pairs']]==ordered
            for row in case['pairs']:
                key=row['pc_i'],row['pc_j']
                check(label+'_pair_'+str(key),row['squared_feature_skew_norm'],values[key],total)
                check(label+'_pair_fraction_'+str(key),row['fraction_of_shared_feature_skew_squared'],values[key]/total)
            i,j=ordered[0];feature=np.array([(u[d,i]*u[d,i]+u[d,j]*u[d,j])/2 for d in range(4*h)])
            harmonic=np.array([feature[2*t]+feature[2*t+1]+feature[2*h+t]+feature[3*h+t] for t in range(h)])
            check(label+'_all_feature_loads',data['feature_load'],feature)
            check(label+'_all_harmonic_loads',data['harmonic_load'],harmonic)
            check(label+'_unit_load',math.fsum(feature),1.)
            q=raw.reshape(n,h,2,2);z=q[...,0]+1j*q[...,1]
            check(label+'_all_complex_source_coefficients',data['source_complex'],z)
            mean=z.mean(axis=0)
            power=np.array([math.fsum(float(q[t,o,c,a])**2 for t in range(n) for c in (0,1) for a in (0,1))/(2*n) for o in range(h)])
            variation=np.array([math.fsum(float((z[t,o,c]-mean[o,c]).real)**2+float((z[t,o,c]-mean[o,c]).imag)**2 for t in range(n) for c in (0,1))/(2*n) for o in range(h)])
            scale=math.fsum(power)
            check(label+'_all_mean_power',data['mean_coefficient_power'],power,scale)
            check(label+'_all_variation_power',data['variation_coefficient_power'],variation,scale)
            top=sorted(range(h),key=lambda t:(-harmonic[t],t))[:8]
            strong=sorted(range(h),key=lambda t:(-variation[t],t))[:8]
            assert meta['top8_feature_loading_harmonics']==[t+1 for t in top]
            assert meta['top8_variation_coefficient_power_harmonics']==[t+1 for t in strong]
            expected=dict(top8_feature_loading_mean_coefficient_power_fraction=math.fsum(power[t] for t in top)/math.fsum(power),
                top8_feature_loading_variation_coefficient_power_fraction=math.fsum(variation[t] for t in top)/math.fsum(variation),
                top8_variation_coefficient_power_fraction=math.fsum(variation[t] for t in strong)/math.fsum(variation),
                leading_pair_squared_feature_skew_fraction=values[ordered[0]]/total,
                first3_pair_squared_feature_skew_fraction=math.fsum(values[t] for t in ordered[:3])/total)
            for name,value in expected.items():check(label+'_'+name,meta[name],value)
            groups=[list(range(ch,2*h,2)) for ch in (0,1)]+[list(range(2*h,3*h)),list(range(3*h,4*h))]
            check(label+'_feature_groups',meta['leading_pair_feature_group_fractions'],[math.fsum(feature[t] for t in g) for g in groups])
            starts=list(range(0,len(positions)-4096+1,256));centers=np.array([positions[t+2048] for t in starts])
            spans=np.array([positions[t+4095]-positions[t] for t in starts])
            root=np.array([1/(512*(positions[t+2049]-positions[t+2047])) for t in starts])
            assert len(starts)==n==meta['rows'] and len(positions)//4096==meta['maximum_disjoint_windows']
            for name,value in (('window_starts',starts),('physical_centers',centers),('window_spans',spans),('observed_root_estimate',root)):
                check(label+'_'+name,data[name],value)
            steps=np.diff(centers)
            expected=dict(coefficient_center_span_seconds=centers[-1]-centers[0],original_query_span_seconds=positions[-1]-positions[0],
                physical_center_step_seconds_min=min(steps),physical_center_step_seconds_max=max(steps),
                source_window_seconds_min=min(spans),source_window_seconds_max=max(spans),
                observed_acoustic_root_Hz_min=min(root),observed_acoustic_root_Hz_max=max(root),
                renderer_step_seconds=1/(4*meta['renderer_root_Hz']),
                maximum_center_step_relative_renderer_difference=max(abs(steps*4*meta['renderer_root_Hz']-1)))
            singular=linalg.svdvals(pc[:-1]);check(label+'_design_singular',data['past_design_singular_values'],singular)
            expected['past_PC_design_condition']=singular[0]/singular[-1]
            assert meta['past_PC_design_rank']==int(np.sum(singular>max(pc[:-1].shape)*np.finfo(float).eps*singular[0]))
            for name,value in expected.items():check(label+'_'+name,meta[name],value)
            common,relative=coords[:,:h],coords[:,h:]
            reconstructed=np.empty_like(z)
            for t in range(n):
                for o in range(h):
                    for ch in (0,1):
                        angle=float(common[t,o]+(.5 if ch==0 else -.5)*relative[t,o])
                        amplitude=math.hypot(float(q[t,o,ch,0]),float(q[t,o,ch,1]))
                        reconstructed[t,o,ch]=amplitude*complex(math.cos(angle),math.sin(angle))
            assert abs(reconstructed-z).max()<2e-12
            r['cases'].append(dict(label=label,pairs_checked=len(values),harmonics_checked=h,all_physical_centres_verified=True))
            save(a.out/'report.json',r);print('SOURCE_SUPPORT_AUDIT',label,flush=True)
        r.update(result='independent_saved_phase_source_support_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_comparison_error=max(r['errors'].values()),
            no_source_training_audio_C_or_mechanical_cause_qualification=True)
        save(a.out/'report.json',r);print(r['result'],r['maximum_comparison_error'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
