"""Independent analytic controls, direct DFT, polynomial Wick moments and C sums."""
import argparse
import cmath
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal
    from local_atlas_v1.oracle import clock, sparse
    from idle_texture_v1.profile import load as model_load
    from local_voice_batch_v1.audit_kernels import rebuild
    a.out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.out/'executed_audit.py')
    result = dict(result='running',cases=[],max_moment_error=0.,max_direct_DFT_error=0.,
                  direct_DFT_complex_values=0,max_direct_source_rebuild_error_FS=0.,max_C_sparse_error_FS=0.,C_renders=0,
                  max_mean_normalized_moment_error=0.)
    try:
        report = load(a.study/'report.json')
        assert report['result'] in ('known_AM_PM_geometry_observed','six_F3_coefficient_geometries_observed')
        for n,h in report['sources'].items():
            assert sha(repo/n) == sha(a.study/'exact_sources'/n) == h
        for n,h in report['inputs'].items():
            assert sha(n) == h
        plan = load(a.study/'exact_sources/research/coefficient_geometry_v1_plan.json')
        gates, cfg = plan['gates'],plan['known']
        def check(actual,expected,scale=None):
            error = abs(actual-expected)
            assert np.all(error <= gates['moments_absolute']+gates['moments_relative']*abs(expected)),float(error.max())
            result['max_moment_error'] = max(result['max_moment_error'],float(error.max()))
            if scale is not None:
                normalized = error/scale
                assert np.all(normalized <= gates['moments_relative']),float(normalized.max())
                result['max_mean_normalized_moment_error'] = max(result['max_mean_normalized_moment_error'],float(normalized.max()))
        def indexes(root):
            return [np.array([4*(h-1)+2*c+j for h in range(1,289) if lo <= h*root < hi for j in (0,1)],dtype=int)
                    for lo,hi in plan['bands_hz'] for c in (0,1)]
        def polynomial(model,groups,interpolation):
            h,k = model['basis'].shape[:2]
            polys = [np.zeros((h*4,h*4)) for _ in range(3)]
            def weights(r):
                return [3/(2+r),6*(r-1)/(2+r),6*(1-r)/(2+r)] if interpolation else [1.,0.,0.]
            for j in range(k):
                v = model['basis'][:,j,:].ravel()
                for n,w in enumerate(weights(model['rho'][j])):
                    polys[n] += w*np.outer(v,v)
            for j in range(h):
                R = model['root'][j]
                # Independent column-outer reconstruction of the residual factor.
                block = sum(np.outer(R[:,q],R[:,q]) for q in range(4))
                for n,w in enumerate(weights(model['residual_rho'][j])):
                    polys[n][j*4:j*4+4,j*4:j*4+4] += w*block
            mean = model['mean'].ravel()
            q = np.array([[sum(float(C[i,i]) for i in g)/2 for g in groups] for C in polys])
            q[0] += np.array([math.fsum(float(mean[i]**2) for i in g)/2 for g in groups])
            expected_mean = sum(q[n]/(n+1) for n in range(3))
            conditional = np.zeros((len(groups),len(groups)))
            ripple = sum(np.outer(q[i],q[j])/(i+j+1) for i in range(3) for j in range(3))-np.outer(expected_mean,expected_mean)
            for i,g in enumerate(groups):
                for j,v in enumerate(groups):
                    blocks = [C[np.ix_(g,v)] for C in polys]
                    conditional[i,j] = math.fsum(float(np.einsum('ab,ab',blocks[n],blocks[m]))/(2*(n+m+1)) for n in range(3) for m in range(3))
                    conditional[i,j] += math.fsum(float(mean[g]@blocks[n]@mean[v])/(n+1) for n in range(3))
            return expected_mean,conditional+ripple,conditional,ripple
        def audit_moments(folder,row,expected_rows=None):
            assert sha(folder/'moments.npz') == row['arrays_sha256']
            d = np.load(folder/'moments.npz')
            values = d['rows']
            if expected_rows is not None:
                assert abs(values-expected_rows).max() <= gates['known_rows_absolute']
            groups = indexes(row['root_hz'])
            q = np.array([[math.fsum(float(x*x) for x in v[g])/2 for g in groups] for v in values])
            energy = q.mean(axis=0)
            assert (energy > 0).all()
            covariance_scale = np.outer(energy,energy)
            check(d['empirical_values'],q,energy)
            check(d['empirical_mean'],energy,energy)
            check(d['empirical_covariance'],np.cov(q,rowvar=False,ddof=0),covariance_scale)
            # Full population Gaussian via observation-space Grams, not D-by-D covariance.
            mean = values.mean(axis=0)
            centered = values-mean
            gram = [centered[:,g]@centered[:,g].T/len(values) for g in groups]
            projected = [centered[:,g]@mean[g] for g in groups]
            cov = np.array([[np.einsum('ab,ba',g,h)/2+projected[i]@projected[j]/len(values)
                             for j,h in enumerate(gram)] for i,g in enumerate(gram)])
            check(d['population_gaussian_mean'],np.mean(q,axis=0),energy)
            check(d['population_gaussian_covariance'],cov,covariance_scale)
            model = {n:d['model_'+n] for n in ('mean','basis','rho','root','residual_rho')}
            for key,interp in [('model_checkpoint',False),('model_interpolation',True)]:
                m,c,conditional,ripple = polynomial(model,groups,interp)
                check(d[key+'_mean'],m,energy)
                check(d[key+'_covariance'],c,covariance_scale)
                if interp:
                    check(d[key+'_conditional_covariance'],conditional,covariance_scale)
                    check(d[key+'_mean_ripple_covariance'],ripple,covariance_scale)
            return values,d
        if report['stage'] == 'known':
            # Direct closed-form fourth moments for ALL hot harmonics/channels.
            for row in report['cases']:
                name = row['label']
                folder = a.study/name
                expected = np.zeros((64,288*4))
                for n in range(64):
                    for j,h in enumerate(cfg['orders']):
                        for c in (0,1):
                            am = cfg['AM_sign'][n%4] if name in ('AM_only','AM_PM') else 0
                            pm = cfg['PM_sign'][n%4] if name in ('PM_only','AM_PM') else 0
                            amp = cfg['amplitudes_L'][j]*(cfg['right_amplitude_ratio'] if c else 1)
                            z = cmath.rect(amp*(1+cfg['AM_depth']*am),cfg['base_phase_L'][j]+c*cfg['right_phase_offset']+cfg['PM_radians']*pm)
                            expected[n,4*(h-1)+2*c:4*(h-1)+2*c+2] = z.real,z.imag
                values,d = audit_moments(folder,row,expected)
                amps = np.array([v*(cfg['right_amplitude_ratio'] if c else 1) for v in cfg['amplitudes_L'] for c in (0,1)])
                depth = cfg['AM_depth'] if name in ('AM_only','AM_PM') else 0.
                delta = cfg['PM_radians'] if name in ('PM_only','AM_PM') else 0.
                m = amps**2*(1+depth**2)/2
                true_cov = np.outer(amps**2,amps**2)*depth**2
                c,s = math.cos(delta),math.sin(delta)
                multiplier = (depth**4*c**4+(1+depth**2)**2*s**4)/2+depth**2*c**4
                gaussian_cov = np.outer(amps**2,amps**2)*multiplier
                check(d['empirical_mean'],m)
                check(d['empirical_covariance'],true_cov)
                check(d['population_gaussian_covariance'],gaussian_cov)
                for render in row['renders']:
                    seed = render['seed'];prefix = folder/f'C_seed{seed}'
                    for suffix,h in render['C_files_sha256'].items():
                        assert sha(prefix.with_suffix(suffix)) == h
                    wave,rate = sf.read(prefix.with_suffix('.wav'),always_2d=True)
                    assert rate == 48000
                    events = np.array([[0.,64.,1.,1.]])
                    roots,phases,_ = clock(events,len(wave))
                    indices = sorted(set(np.linspace(0,len(wave)-1,48).astype(int).tolist()+[0,1,187,188,189,374,375,376,47999,48000,48001]))
                    model,root = model_load(folder/'voice.model')
                    want,updates = sparse([model],np.array([root]),[0.],seed,roots,phases,indices)
                    error = abs(wave[indices]-want)
                    bound = .5001*np.spacing(abs(want.astype('float32'))).astype(float)+2e-9
                    assert np.all(error <= bound),float((error-bound).max())
                    result['max_C_sparse_error_FS'] = max(result['max_C_sparse_error_FS'],float(error.max()))
                    assert load(prefix.with_suffix('.json'))['texture_updates'] == [updates]
                    arrays = folder/f'wave_seed{seed}.npz'
                    assert sha(arrays) == render['wave_arrays_sha256']
                    w = np.load(arrays)
                    assert np.array_equal(w['audio'],wave[cfg['C_analysis_first']:])
                    native = load(a.workspace/'baselines/F3_joint_envelopes_v1/source/research/F3_joint_envelopes_v1_plan.json')
                    spec = native['measurement'];n=spec['window_samples'];fft=spec['fft_samples']
                    frames = w['audio'][w['window_starts'][:,None]+np.arange(n)]
                    freq,psd = signal.welch(frames,fs=48000,window='hann',nperseg=n,noverlap=0,nfft=fft,detrend=False,axis=1)
                    power = np.stack([psd[:,(freq>=lo)&(freq<hi)].sum(axis=1)*48000/fft for lo,hi in spec['bands_hz']],axis=1)
                    check(w['P'].diagonal(axis1=-2,axis2=-1).real,power)
                    # The independently checked FFT powers differ at roundoff.
                    # Re-log the literal producer matrix for the covariance
                    # audit: near-empty bands amplify a new FFT's roundoff.
                    literal = w['P'].diagonal(axis1=-2,axis2=-1).real
                    feature = np.array([[10*math.log10(max(float(v),native['features']['log_floor_FS2']))
                                         for v in frame.flat] for frame in literal])
                    check(w['log_power_dB'],feature)
                    t=(w['window_starts']+n/2)/48000;t-=t.mean()
                    residual=feature-feature.mean(axis=0)-t[:,None]*(t@feature)/(t@t)
                    check(w['affine_residual_covariance'],np.cov(residual,rowvar=False,ddof=0))
                    result['C_renders'] += 1
                if name == cfg['block_identity_case']:
                    assert sha(folder/'C_block37.wav') == row['renders'][0]['C_files_sha256']['.wav']
                result['cases'].append(dict(label=name,analytic_population_and_polynomial_moments_verified=True))
                save(a.out/'report.json',result)
                print('PASS independent analytic/C geometry',name,flush=True)
        else:
            for row in report['cases']:
                folder = a.study/row['label']
                assert sha(folder/'source.npz') == row['source_arrays_sha256']
                d = np.load(folder/'source.npz')
                direct = rebuild(d['native'],row['source_start'],d['positions'],row['cutoff_hz'])
                error = float(abs(direct-d['rebuilt']).max())
                assert error <= gates['coefficient_DFT_absolute']
                result['max_direct_source_rebuild_error_FS'] = max(result['max_direct_source_rebuild_error_FS'],error)
                assert np.array_equal(d['rebuilt'].astype('float32').astype(float),d['normalized_FLOAT'])
                normalized = d['rebuilt'];n=4096
                window = signal.windows.hann(n,sym=False)
                order = np.arange(1,289)
                kernel = np.exp(-2j*np.pi*order[:,None]*np.arange(n)/1024)*window[None,:]*2/math.fsum(window)
                starts = np.arange(0,len(normalized)-n+1,256)
                direct_coeff = np.stack([(kernel@normalized[start:start+n])*np.exp(-2j*np.pi*order*start/1024)[:,None] for start in starts])
                original,_ = audit_moments(folder/'full',row['variants'][0])
                z = original.reshape(len(original),288,2,2)
                z = z[...,0]+1j*z[...,1]
                error = float(abs(direct_coeff-z).max())
                assert error <= gates['coefficient_DFT_absolute']
                result['max_direct_DFT_error'] = max(result['max_direct_DFT_error'],error)
                result['direct_DFT_complex_values'] += z.size
                for variant in row['variants'][1:]:
                    modified = np.empty_like(z)
                    for h in range(288):
                        for c in (0,1):
                            vals = [complex(v) for v in z[:,h,c]]
                            rms = math.sqrt(math.fsum(abs(v)**2 for v in vals)/len(vals))
                            mean = sum(vals)/len(vals)
                            phase = cmath.phase(mean) if abs(mean)>1e-15 else 0.
                            for i,v in enumerate(vals):
                                modified[i,h,c] = cmath.rect(rms,cmath.phase(v)) if variant['label']=='phase_only' else cmath.rect(abs(v),phase)
                    expected = np.stack([modified.real,modified.imag],axis=-1).reshape(len(z),-1)
                    audit_moments(folder/variant['label'],variant,expected)
                result['cases'].append(dict(label=row['label'],variants=3,original_DOUBLE_FLOAT_and_all_DFT_verified=True))
                save(a.out/'report.json',result)
                print('PASS independent native F3 coefficient geometry',row['label'],flush=True)
        result.update(result='independent_coefficient_geometry_audit_passed',stage=report['stage'],
                      producer_report_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),timbre_or_runtime_replacement_qualified=False)
    except Exception as exc:
        result.update(result='failed',error=repr(exc))
        raise
    finally:
        save(a.out/'report.json',result)


if __name__ == '__main__':
    main()
