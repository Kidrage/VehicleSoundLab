"""Independent new-method consumer identity, all-bin observations and changes."""
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
    import numpy as np
    from scipy import signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_errors={},inputs={})
    def check(name,left,right,scale=1.,gate=2e-11):
        left,right=np.asarray(left),np.asarray(right)
        assert left.shape==right.shape,(name,left.shape,right.shape)
        if scale==0:
            assert np.count_nonzero(left)==np.count_nonzero(right)==0;error=0.
        else:error=float(np.max(abs(left-right))/scale) if left.size else 0.
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<gate,(name,error,gate)
    def db(left,right):
        out=[]
        for l,row in zip(left,right):
            out.append([float(10*np.log10(x/y)) if x>0 and y>0 else None for x,y in zip(l,row)])
        return out
    def mixed(name,left,right):
        left,right=np.asarray(left,object),np.asarray(right,object)
        assert left.shape==right.shape
        for x,y in zip(left.ravel(),right.ravel()):
            if x is None or y is None:assert x is y,(name,x,y)
            else:check(name,x,y)
    try:
        source=load(a.study/'report.json')
        assert source['result'] in ('locked_source_known_virtual_measured','locked_source_real_virtual_measured')
        for name,digest in source['sources'].items():assert sha(a.study/'exact_sources'/name)==digest
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        for case in source['cases']:
            path=a.study/case['report'];assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            study=load(path);assert study['result']=='locked_source_virtual_case_measured'
            for name,digest in study['inputs'].items():assert sha(name)==digest
            bound=study['source'];binding=Path(bound['binding_file']);assert sha(binding)==bound['binding_sha256']
            cases=[Path(name) for name in study['inputs'] if Path(name).name=='capture.npz']
            assert len(cases)==1;capture=cases[0]
            with np.load(capture) as f:z={name:f[name] for name in f.files}
            assert sha(capture)==bound['capture_sha256']
            assert np.array_equal(z['audio'][2048:-2048],z['target'])
            proofs=[load(name) for name in study['inputs'] if Path(name).name=='report.json']
            if bound['known_control']:
                math=next(x for x in proofs if x.get('result')=='independent_locked_source_known_verified')
                control=next(x for x in math['cases'] if x['label']==case['label'])
                assert math['all_qualified'] and control['all_qualified']
                assert math['producer_sha256']==sha(binding)
                complete_path=next(Path(name) for name in study['inputs']
                    if Path(name).name==control['complete_audit_file'])
                row=load(complete_path)
                assert math['inputs'][str(capture)]==sha(capture)
                case_report=next(Path(name) for name in study['inputs']
                    if Path(name).parent==capture.parent and Path(name).name=='report.json')
                assert math['inputs'][str(case_report)]==sha(case_report)
            else:
                math=next(x for x in proofs if x.get('result')=='independent_locked_source_real_verified')
                assert math['verification_passed']
                row=math['case']
                spec=load(binding)
                assert spec['schema']=='vsl.locked_source_real_spec/1' and spec['declared_cases']==[case['label']]
                assert spec['only_one_finite_case'] and case['label']!='F3 Fifth First Early'
            assert math['inputs'][str(binding)]==sha(binding)
            assert row['result']=='independent_locked_source_case_verified' and row['verification_passed']
            assert np.isfinite(z['metric_target']).all() and z['metric_target'].shape==z['target'].shape
            assert study['source']['method']=='sinc128 new audio fitted with explicit unchanged legacy metric_target'
            for field in ('solver_qualified','fidelity_qualified','capture_sha256','producer_sha256'):
                key='case_report_sha256' if field=='producer_sha256' else field
                assert row[field]==bound[key]
            assert study['meter_protocol']['protocol']=='independent_extraction_sound_composition_verified'
            assert not study['meter_protocol']['legacy_cross_operator_all_statistics_qualified']
            assert study['meter_protocol']['retained_legacy_normalized_failure_count']==5
            assert [x['region'] for x in study['regions']]==['new_target','complete_genuine_context']
            signed_count=0
            for region,part in zip(study['regions'],(slice(2048,-2048),slice(None))):
                file=path.parent/region['file'];assert sha(file)==region['sha256']
                with np.load(file) as f:out={name:f[name] for name in f.files}
                assert np.array_equal(out['reference_audio'],z['audio'][part])
                assert np.array_equal(out['candidate_audio'],z['wave'][part])
                for label in ('reference','candidate'):
                    audio=out[label+'_audio'];N=4096;hop=256;rate=65536
                    starts=np.arange(0,len(audio)-N+1,hop)
                    assert np.array_equal(out[label+'_starts'],starts)
                    raw=np.array([audio[s:s+N] for s in starts]);w=signal.windows.hann(N,sym=False)
                    frequency,power=signal.welch(raw,fs=rate,window=w,nperseg=N,noverlap=0,detrend=False,scaling='density',axis=1)
                    ids=np.searchsorted([3000,6000,8000,10000,14000],frequency,side='right')
                    broad=np.stack([power[:,ids==b].sum(axis=1)*rate/N for b in range(6)],axis=1)
                    energy=float(np.max(broad))
                    check('independent_actual_broad_power',out[label+'_broad_power'],broad,energy)
                    bins=(4*z['orders']).astype(int)
                    bands=np.searchsorted([3000,6000,8000,10000,14000],64*z['orders'],side='right')
                    line=np.stack([power[:,bins[bands==b]].sum(axis=1)*(rate*np.dot(w,w)/w.sum()**2) for b in range(6)],axis=1)
                    check('independent_actual_line_power',out[label+'_line_power'],line,energy)
                    for prefix in ('broad','line'):
                        quality=region[label+'_precision'][prefix]
                        for field,value in quality.items():
                            assert np.array_equal(np.asarray(value),out[label+'_'+prefix+'_'+field])
                for prefix in ('broad','line'):
                    changed=region['signed_changes'][prefix]
                    get=lambda which,field:out[which+'_'+prefix+'_'+field]
                    for field,title in (('mean_power','power'),('mean_mid_side','mid_side')):
                        expected=get('candidate',field)-get('reference',field)
                        scale=max(float(np.max(abs(get(which,field)))) for which in ('candidate','reference'))
                        check(prefix+'_'+title+'_signed',changed[title+'_change_FS2'],expected,scale)
                        mixed(prefix+'_'+title+'_db',changed[title+'_change_dB'],db(get('candidate',field),get('reference',field)))
                        signed_count+=expected.size
                    for field in ('CV','complex_coherence'):
                        maskfield='power_defined' if field=='CV' else 'coherence_defined'
                        mask=get('reference',maskfield)&get('candidate',maskfield)
                        delta=get('candidate',field)-get('reference',field)
                        if field=='CV':expected=np.where(mask,delta,None).tolist()
                        else:expected=[[float(x.real),float(x.imag)] if valid else None for x,valid in zip(delta,mask)]
                        mixed(prefix+'_'+field+'_change',changed[field+'_change'],expected)
                    for field in ('covariance','lag_covariance'):
                        delta=get('candidate',field)-get('reference',field)
                        scale=max(float(np.max(abs(get(which,field)))) for which in ('candidate','reference'))
                        check(prefix+'_'+field+'_signed',changed[field+'_signed_change_FS4'],delta,scale)
                        denominator=np.sqrt(np.sum(get('reference',field)**2))
                        expected=float(np.sqrt(np.sum(delta**2))/denominator) if denominator else None
                        mixed(prefix+'_'+field+'_relative',changed[field+'_relative_difference'],expected)
                        signed_count+=delta.size
            if 'native_recording' in study:
                from native_clock_case_audit_v1.sound import verify as audit_native
                raw_file=path.parent/study['native_recording']['file']
                assert sha(raw_file)==study['native_recording']['sha256']
                with np.load(raw_file) as saved:raw={name:saved[name] for name in saved.files}
                assert np.array_equal(raw['audio'],z['native'])
                gates=load(a.study/'exact_sources/research/native_clock_case_v1_plan.json')['gates']
                audit_native('raw',raw['audio'],{'raw_'+key:value for key,value in raw.items()},check,gates)
                for prefix,values in study['native_recording']['precision'].items():
                    for key,value in values.items(): assert np.array_equal(value,raw[prefix+'_'+key])
            r['cases'].append(dict(label=case['label'],all_consumer_checks_passed=True,
                target_and_context_checked=True,signed_linear_changes_checked=signed_count,
                source_solver_qualified=bound['solver_qualified'],source_fidelity_qualified=bound['fidelity_qualified']))
            save(a.out/'report.json',r)
            print('LOCKED_VIRTUAL_AUDIT',case['label'],'PASS',flush=True)
        if source['result']=='locked_source_known_virtual_measured':
            assert len(r['cases'])==3 and len(source['guard_rejections'])==6
            assert {x['control'] for x in source['guard_rejections']}=={
                'verification','kind','case_hash','capture_hash','qualification_flag','spec_binding'}
        r.update(result='independent_locked_source_virtual_verified',all_consumer_checks_passed=True,
            producer_sha256=sha(a.study/'report.json'),producer_meter_and_consumer_not_imported=True,
            actual_recorded_diagnostics_verified=source['result']=='locked_source_real_virtual_measured',
            native_inverse_render_or_hearing_qualified=False,auditor_sha256=sha(__file__),
            signed_power_covariance_gates_use_actual_nonzero_field_scales=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
