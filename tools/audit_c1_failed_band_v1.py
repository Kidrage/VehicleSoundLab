"""Independent declared-frame, joint LR, cubic-extremum and restriction audit."""
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
    from scipy.interpolate import PPoly
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',comparisons={})
    def check(name,saved,expected,scale=None):
        saved,expected=np.asarray(saved),np.asarray(expected);assert saved.shape==expected.shape,name
        norm=max(float(abs(expected).max()) if scale is None else float(scale),1e-300)
        error=float(abs(saved-expected).max())/norm;r['comparisons'][name]=error
        if not np.isfinite(error) or error>2e-11:raise ValueError((name,error))
    try:
        source=load(a.study/'report.json');assert source['result']=='single_terminal_c1_failed_band_diagnosed'
        repo=Path(__file__).resolve().parents[1]
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():assert sha(name)==digest
        assert source['known']['clock_cases']==3 and len(source['known']['optimality_cases'])==3
        assert len(source['known']['clock_rejections'])==3
        path=next(Path(name) for name in source['inputs'] if Path(name).name=='capture.npz')
        with np.load(path) as f:
            z={k:f[k] for k in ('audio','target','wave','weights','amplitude','orders','clock_x','clock_coefficients')}
        case=load(path.parent/'report.json');audited=load(path.parent.parent/'run1_audit/report.json')
        assert case['solver_qualified'] and not case['fidelity_qualified'] and audited['verification_passed']
        assert np.array_equal(z['orders'],np.arange(1,289))
        assert sha(a.study/'diagnostic.npz')==source['arrays_sha256']
        with np.load(a.study/'diagnostic.npz') as f:data={k:f[k] for k in f.files}
        window=.5-.5*np.cos(2*np.pi*np.arange(4096)/4096)
        endpoint=np.r_[1.,np.full(2047,2.),1.]
        def observe(audio):
            coverage=np.zeros(len(audio))
            for start in range(-3840,len(audio),256):
                ids=np.arange(4096)+start;valid=(ids>=0)&(ids<len(audio))
                coverage[ids[valid]]+=window[valid]**2
            starts=np.arange(0,len(audio)-4096+1,256);normal=1/np.sqrt(coverage)
            rows=[];ordinary=[]
            for start in starts:
                values=audio[start:start+4096]*normal[start:start+4096,None]
                transformed=np.column_stack([np.fft.rfft(values[:,ch]*window)*np.sqrt(endpoint)/64 for ch in (0,1)])
                rows.append(transformed*float(z['amplitude'])*z['weights'][:,None])
                ordinary.append(np.column_stack([np.fft.rfft(audio[start:start+4096,ch]*window) for ch in (0,1)]))
            power=np.mean(abs(np.array(ordinary))**2,axis=0)*endpoint[:,None]/(4096*math.fsum(window*window))
            return np.asarray(rows),power,coverage,starts
        y,yp,coverage,starts=observe(z['target'])
        e,ep,_,_=observe((z['wave']-z['audio'])[2048:-2048])
        whole,_,_,full_starts=observe(z['wave']-z['audio'])
        ids=np.searchsorted(full_starts,starts+2048)
        assert np.array_equal(e,whole[ids])
        for name,value in (('target_reference_rows',y),('target_error_rows',e),('virtual_reference_Welch_FS2',yp),
            ('virtual_error_Welch_FS2',ep),('virtual_coverage',coverage),('virtual_starts',starts),('target_rows_in_whole_context',ids)):
            check(name,data[name],value)
        joint=np.concatenate((y,e),axis=2)
        gram=np.einsum('wki,wkj->kij',joint,joint.conj(),optimize=False)
        check('all_bins_full_joint_LR_Gram',data['virtual_joint_reference_error_Gram'],gram)
        for k in (0,875,1000,1152,1153,1500,2048):
            for i in range(4):
                for j in range(4):
                    products=joint[:,k,i]*joint[:,k,j].conj()
                    direct=complex(math.fsum(products.real),math.fsum(products.imag))
                    check('scalar_Gram_'+str((k,i,j)),data['virtual_joint_reference_error_Gram'][k,i,j],direct,max(float(abs(gram[k]).max()),1e-30))
        refmass=np.sum(abs(y)**2,axis=0);errmass=np.sum(abs(e)**2,axis=0)
        check('reference_all_bins',data['virtual_reference_weighted_mass'],refmass)
        check('error_all_bins',data['virtual_error_weighted_mass'],errmass)
        frequency=np.arange(2049)*16.;band=np.digitize(frequency,[3000,6000,8000,10000,14000])
        masks=[band==i for i in range(6)]+[(frequency>=14000)&(frequency<16000),
            (frequency>=16000)&(frequency<18432),frequency==18432,frequency>18432]
        rows=source['summary']['original_bands']+source['summary']['highest_band_split']
        for i,(mask,row) in enumerate(zip(masks,rows)):
            assert row['bins']==np.count_nonzero(mask)
            rp,er=refmass[mask].sum(axis=0),errmass[mask].sum(axis=0)
            for key,val in (('reference_weighted_mass_LR',rp),('error_weighted_mass_LR',er),
                ('reference_Welch_FS2_LR',yp[mask].sum(axis=0)),('error_Welch_FS2_LR',ep[mask].sum(axis=0)),
                ('combined_complex_NRMSE',np.sqrt(er.sum()/rp.sum()))):check('group'+str(i)+'_'+key,row[key],val)
        for name,mass in (('reference',refmass),('error',errmass)):
            expected=mass[frequency>18432].sum()/mass[frequency>=14000].sum()
            check(name+'_above_fraction',source['summary']['above_centre_'+name+'_fraction_of_highest_weighted_mass'],expected)
        actual=[float(np.linalg.norm(e[:,band==i])/np.linalg.norm(y[:,band==i])) for i in range(6)]
        assert max(abs(np.array(actual)-case['metrics']['target_supported_band_complex_NRMSE']))<2e-12
        derivative=PPoly(z['clock_coefficients'],z['clock_x'],extrapolate=False).derivative()
        roots=derivative.derivative().roots(extrapolate=False);roots=roots[np.isfinite(roots)]
        extrema=[]
        for start in starts:
            lo,hi=start+2048,start+2048+4095
            candidates=np.r_[lo,hi,z['clock_x'][(z['clock_x']>lo)&(z['clock_x']<hi)],roots[(roots>lo)&(roots<hi)]]
            values=derivative(candidates);assert min(values)>0
            extrema.append([min(values),max(values)])
        extrema=np.asarray(extrema)
        check('all_window_clock_derivative_bounds',data['clock_derivative_bounds'],extrema)
        correspondence=frequency[None,:,None]/(65536*extrema[:,None,::-1])
        check('all_single_tone_frequency_correspondences',data['constant_coordinate_tone_physical_Hz_envelopes'],correspondence)
        summary=source['summary'];opt=summary['nominal_original_optimality']
        high=frequency>=14000;ref=float(np.linalg.norm(y[:,high]));error=float(np.linalg.norm(e[:,high]))
        gap=max(case['residual_certificate']['gap_upper_bound'],audited['case']['residual_certificate']['gap_upper_bound'])
        for key,value in (('highest_band_reference_norm',ref),('highest_band_residual_norm',error),
            ('inherited_gap_upper_bound',gap),('inherited_weighted_distance_bound',np.sqrt(gap)),
            ('maximum_possible_highest_NRMSE_change',np.sqrt(gap)/ref),
            ('exact_same_objective_optimum_NRMSE_lower_bound',max(0,error-np.sqrt(gap))/ref),('original_highest_NRMSE',error/ref)):
            check('nominal_optimality_'+key,opt[key],value)
        assert opt['original_fidelity_gate']==.02 and opt['inherited_certificate_is_floating_point_not_interval_arithmetic']
        for key,value in (('source_clock_derivative_seconds_per_coordinate_sample_range',[extrema[:,0].min(),extrema[:,1].max()]),
            ('highest_centre_single_tone_physical_Hz_range',[correspondence[:,1152,0].min(),correspondence[:,1152,1].max()])):
            check(key,summary[key],value)
        native=next(Path(name) for name in source['inputs'] if Path(name).name=='measured.npz')
        with np.load(native) as f:
            for name in data:
                if name.startswith('native_'):assert np.array_equal(data[name],f[name.removeprefix('native_')])
        assert not source['original_fidelity_qualified'] and not source['eligible_for_later_source_statistics']
        r.update(result='independent_terminal_c1_failed_band_verified',verification_passed=True,
            producer_sha256=sha(a.study/'report.json'),maximum_comparison_error=max(r['comparisons'].values()),
            nominal_optimality_not_interval_arithmetic=True,new_C1_source_eligible_for_statistics=False,
            no_new_fit_reconstruction_audio_C_or_audible_cause_qualification=True)
        save(a.out/'report.json',r);print(r['result'],len(r['comparisons']),r['maximum_comparison_error'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
