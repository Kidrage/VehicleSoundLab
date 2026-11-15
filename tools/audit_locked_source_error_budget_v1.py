"""Independent all-query interpolation, all-output FIR and signed Gram audit.

Imports neither the new interpolator nor its budget implementation. Original
source fidelity failures remain independent of diagnostic correctness.
"""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','out'):
        p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal,special
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',inputs={},variants=[],auditor_sha256=sha(__file__))
    try:
        source=load(a.study/'report.json')
        assert source['result']=='locked_source_native_error_budget_measured'
        assert source['explicit_new_audio_and_unchanged_legacy_metric_target']
        r['inputs'][str(a.study/'report.json')]=sha(a.study/'report.json')
        for name,digest in source['sources'].items():
            assert sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():
            assert sha(name)==digest
        case=Path(source['source']['binding_file']).parent/source['source']['label']
        with np.load(case/'capture.npz') as f:
            original={k:f[k] for k in ('audio','wave','band_power','floor_active','sigma','amplitude')}
        columns=np.concatenate((original['audio'],original['wave']),axis=1)
        native_path=Path(source['native_study'])/'report.json'
        assert source['inputs'][str(native_path)]==sha(native_path)
        native=load(native_path)
        assert native['result']=='locked_source_native_case_measured'
        native_audit_path=Path(source['native_audit'])/'report.json'
        native_audit=load(native_audit_path)
        assert source['inputs'][str(native_audit_path)]==sha(native_audit_path)
        assert native_audit['result']=='independent_locked_source_native_verified'
        assert native_audit['verification_passed'] and native_audit['producer_sha256']==sha(native_path)
        from locked_source_diagnostics_v1.native_identity import verify as verify_identity
        verify_identity(native,native_path.parent,Path(__file__).resolve().parents[1],r['inputs'])
        for key in ('source_solver_qualified','source_fidelity_qualified',
                    'native16_32_convergence_passed','eligible_for_later_source_statistics'):
            assert source[key]==native[key]
            r[key]=source[key]
        for key in ('band_power','floor_active'):
            assert source['locked_'+key]==original[key].tolist()
        assert source['locked_sigma']==float(original['sigma'])
        assert source['locked_amplitude']==float(original['amplitude'])
        assert source['original_source_metrics']==load(case/'report.json')['metrics']
        assert source['original_native_comparisons']==native['comparisons']
        with np.load(native_path.parent/native['sound']['file']) as f:
            raw,fir=f['raw_audio'],f['FIR_only_audio']
        for row in source['variants']:
            path=a.study/row['file'];assert sha(path)==row['sha256']
            with np.load(path) as f:z={k:f[k] for k in f.files}
            up,radius=row['up'],row['radius']
            with np.load(native_path.parent/('render'+str(up)+'.npz')) as f:
                query,kernel,continuous=f['query'],f['taps'],f['native']
            assert np.array_equal(raw,z['raw']) and np.array_equal(fir,z['FIR_only'])
            assert np.array_equal(continuous,z['continuous_OSC'])
            # Independent accumulation over offsets and a separate I0 kernel;
            # every query is checked, not only selected plotted sample points.
            reconstructed=np.empty((len(query),4))
            for first in range(0,len(query),4096):
                u=query[first:first+4096]
                centers=np.trunc(u).astype(np.int64)
                total=np.zeros((len(u),4));normalizer=np.zeros(len(u))
                for offset in range(1-radius,radius+1):
                    ids=centers+offset
                    assert ids.min()>=0 and ids.max()<len(columns)
                    d=u-ids
                    sinc=np.divide(np.sin(np.pi*d),np.pi*d,out=np.ones_like(d),where=d!=0)
                    w=sinc*special.i0(12*np.sqrt(1-(d/radius)**2))/special.i0(12.)
                    total+=w[:,None]*columns[ids];normalizer+=w
                reconstructed[first:first+len(u)]=total/normalizer[:,None]
            physical=signal.upfirdn(kernel,reconstructed,down=up,axis=0)[256:256+len(raw)]
            stored=np.concatenate((z['phase_reconstruction'],z['fitted_grid_reconstruction']),axis=1)
            sample_scale=float(np.max(abs(columns)))
            sample_error=float(np.max(abs(physical-stored))/sample_scale)
            assert sample_error<2e-11,(radius,up,sample_error)
            components=np.stack((fir-raw,z['phase_reconstruction']-fir,
                z['fitted_grid_reconstruction']-z['phase_reconstruction'],
                continuous-z['fitted_grid_reconstruction']),axis=1)
            assert np.array_equal(components,z['components'])
            total_error=continuous-raw
            assert np.array_equal(total_error,z['total_error'])
            assert np.array_equal(total_error-components.sum(axis=1),z['closure'])
            assert np.max(abs(z['closure']))<=2e-15
            c=components.reshape(len(raw),8)
            starts=list(range(0,len(raw)-4096+1,256))
            assert np.array_equal(starts,z['starts'])
            window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
            X=np.array([np.fft.rfft(c[start:start+4096]*window[:,None],axis=0) for start in starts])
            Y=np.array([np.fft.rfft(raw[start:start+4096]*window[:,None],axis=0) for start in starts])
            E=np.array([np.fft.rfft(total_error[start:start+4096]*window[:,None],axis=0) for start in starts])
            weights=np.r_[1.,np.full(2047,2.),1.]
            groups=np.searchsorted([3000,6000,8000,10000,14000],np.arange(2049)*48000/4096,side='right')
            errors=[]
            for band in range(6):
                mask=groups==band;w=np.tile(weights[mask],len(starts))
                data=X[:,mask].reshape(-1,8)
                gram=np.array([[np.vdot(data[:,j],data[:,i]*w) for j in range(8)] for i in range(8)])
                gram_scale=float(np.max(abs(gram)))
                gram_error=float(np.max(abs(gram-z['band_joint_Gram'][band]))/gram_scale) if gram_scale else 0.
                assert gram_error<2e-11,(band,gram_error)
                autos=np.array([[gram[2*i+c,2*i+c].real for c in range(2)] for i in range(4)])
                crosses=np.zeros((4,4,2))
                for i in range(4):
                    for j in range(i+1,4):
                        crosses[i,j]=[2*gram[2*i+c,2*j+c].real for c in range(2)]
                rp=np.array([np.sum(abs(Y[:,mask,c])**2*weights[mask]) for c in range(2)])
                ep=np.array([np.sum(abs(E[:,mask,c])**2*weights[mask]) for c in range(2)])
                recovered=autos.sum(axis=0)+crosses.sum(axis=(0,1))
                scale=autos.sum(axis=0)+abs(crosses).sum(axis=(0,1))
                closure_error=np.divide(abs(ep-recovered),scale,out=np.zeros_like(scale),where=scale>0)
                assert np.max(closure_error)<2e-12
                for name,wanted in (('band_component_auto_power',autos),('band_component_signed_cross_power',crosses),
                                    ('band_reference_power',rp),('band_error_power',ep),('band_recovered_error_power',recovered)):
                    delta=np.max(abs(z[name][band]-wanted))
                    bound=max(float(np.max(abs(wanted))),float(np.max(scale)))
                    assert delta<=2e-11*bound,(name,delta,bound)
                ratios=[float(np.sqrt(e/p)) if p>0 else (0. if e==0 else None) for e,p in zip(ep,rp)]
                assert np.max(abs(np.asarray(ratios)-row['band_error_NRMSE_LR'][band]))<2e-11
                errors.append(dict(band=band,Gram_relative_error=gram_error,
                                   signed_power_equation_error=float(np.max(closure_error))))
            expected=np.array([[sum(c[:,i]*c[:,j]) for j in range(8)] for i in range(8)])
            assert np.max(abs(expected-z['time_joint_Gram']))<2e-11*np.max(abs(expected))
            r['variants'].append(dict(radius=radius,up=up,all_query_and_all_output_FIR_relative_error=sample_error,
                                      bands=errors,all_component_and_signed_Gram_fields_verified=True))
            save(a.out/'report.json',r)
            print('LOCKED_SOURCE_ERROR_AUDIT',radius,up,'PASS',flush=True)
        assert [(v['radius'],v['up']) for v in source['variants']]==[(32,16),(64,16),(128,16),(128,32)]
        r.update(result='independent_locked_source_native_error_budget_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),source_failure_not_promoted=True,
            no_C_or_sustained_voice_or_physical_inverse_qualification=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':
    main()
