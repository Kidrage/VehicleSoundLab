"""Full288 known native rendering; no real capture, source fit or C promotion."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from native_clock_render_v1.fixtures import specs,make,phase
    from native_clock_render_v1.filter import render,taps
    from native_clock_render_v1.basis import evaluate
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',cases=[],sources={},inputs={},FIR=[],guards=[])
    try:
        plan=load(repo/'research/native_clock_render_v1_plan.json');gates=plan['gates']
        names=['tools/run_native_clock_render_known_v1.py','tools/audit_native_clock_render_known_v1.py',
            'research/native_clock_render_v1_plan.json','tools/research_archive_v1.py']
        names.extend(p.relative_to(repo).as_posix() for p in (repo/'tools/native_clock_render_v1').glob('*.py'))
        for name in names:
            path=a.out/'exact_sources'/name;path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,path);r['sources'][name]=sha(path)
        spec_path=a.workspace/'references/analysis/waveform_file_real_v1/real1/run_spec.json'
        spec=load(spec_path);r['inputs'][str(spec_path)]=sha(spec_path)
        assert all(sha(repo/name)==digest for name,digest in spec['sources'].items())
        for up in (16,32):
            kernel=taps(up)
            f,h=signal.freqz(kernel,worN=262144,fs=48000*up)
            dc=abs(kernel.sum()-1)
            passband=float(np.max(abs(20*np.log10(abs(h[f<=20000])))))
            stopband=float(np.max(abs(h[f>=24000])))
            r['FIR'].append(dict(up=up,taps=len(kernel),DC_error=float(dc),passband_max_abs_dB=passband,
                stopband_max_magnitude=stopband))
            assert dc<=gates['FIR_DC_error_max']
            assert passband<=gates['FIR_passband_0_to_20000_max_dB']
            assert stopband<=gates['FIR_stopband_24000_to_denseNyquist_max_magnitude']
        save(a.out/'report.json',r)
        for name,s in specs():
            z=make(name,s)
            arrays,geometry=render(z['nodes'],z['positions'],z['orders'],z['source_seconds'],float(z['native_start']),int(z['count']))
            probe=np.unique(np.r_[np.arange(0,len(z['source_seconds']),137),z['positions']]).astype(int)
            arrays['integer_probe_indices']=probe
            arrays['integer_probe_wave']=evaluate(z['nodes'],z['positions'],z['orders'],probe)
            analytic=phase(arrays['dense_times']-17,s)-float(z['phase_origin'])
            error=float(np.max(abs(arrays['query']/1024-analytic)))
            assert error<=gates['declared_coordinate_inverse_vs_analytic_cycles_max']
            if s['zero']:assert np.count_nonzero(arrays['native'])==0
            if s['mono']:assert np.count_nonzero(arrays['native'][:,0]-arrays['native'][:,1])==0
            if s['silent']:assert np.count_nonzero(arrays['native'][:,1])==0
            path=a.out/(name+'.npz');np.savez_compressed(path,**z,**arrays)
            r['cases'].append(dict(label=name,spec=s,file=path.name,sha256=sha(path),geometry=geometry,
                phase_inverse_error_cycles=error,orders=288,nodes=len(z['positions']),active_coefficients_known_only=True))
            save(a.out/'report.json',r);print('NATIVE_CLOCK_KNOWN',name,'PASS phase',error,flush=True)
        base=make('unequal_phase',dict(specs())['unequal_phase'])
        for name in ('nonmonotonic_clock','nonfinite_clock','missing_FIR_context','bad_coefficients',
                     'coefficient_shape','node_order','harmonic_order','fractional_count','zero_count','dense_budget'):
            z={key:value.copy() for key,value in base.items()}
            count=int(z['count']);start=float(z['native_start'])
            if name=='nonmonotonic_clock':z['source_seconds'][10]=z['source_seconds'][9]
            if name=='nonfinite_clock':z['source_seconds'][10]=np.nan
            if name=='missing_FIR_context':start=float(z['source_seconds'][0])
            if name=='bad_coefficients':z['nodes'][0,0,0]=np.nan
            if name=='coefficient_shape':z['nodes']=z['nodes'][:,:,:1]
            if name=='node_order':z['positions'][1]=z['positions'][0]
            if name=='harmonic_order':z['orders'][1]=z['orders'][0]
            if name=='fractional_count':count=12.5
            if name=='zero_count':count=0
            if name=='dense_budget':z['source_seconds'][10]=z['source_seconds'][9]+1e-12
            try:render(z['nodes'],z['positions'],z['orders'],z['source_seconds'],start,count)
            except ValueError as error:r['guards'].append(dict(label=name,rejected=str(error)))
            else:raise AssertionError('Invalid input accepted: '+name)
        assert all(sha(repo/name)==digest for name,digest in spec['sources'].items())
        r.update(result='native_clock_render_known_measured',all_phase_and_FIR_gates_passed=True,
            live_fit_sources_unchanged=True,no_real_fit_or_sustained_source_or_C_or_hearing_promotion=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
