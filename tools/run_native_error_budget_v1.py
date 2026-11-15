"""Known-first actual signed error budget; no fitting or voice promotion."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','out'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--known-check',action='store_true')
    p.add_argument('--known-study',type=Path)
    p.add_argument('--source-study',type=Path)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import signal
    from native_error_budget_v1.interpolate import reconstruct
    from native_error_budget_v1.budget import analyze
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False)
    r=dict(result='running',sources={},inputs={},variants=[])
    try:
        names={'tools/run_native_error_budget_v1.py','research/native_error_budget_v1_plan.json','tools/research_archive_v1.py'}
        for folder in ('native_error_budget_v1','native_clock_render_v1','native_clock_case_v1','extraction_sound_v1'):
            names.update(p.relative_to(repo).as_posix() for p in (repo/'tools'/folder).glob('*.py'))
        for name in sorted(names):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        if a.known_check:
            from native_error_budget_v1.known import qualify
            r.update(result='native_error_budget_known_qualified',known=qualify(),all_known_qualified=True)
            save(a.out/'report.json',r);print('NATIVE_ERROR_BUDGET_KNOWN_PASS',flush=True);return
        if a.known_study is None or a.source_study is None:
            raise ValueError('Qualified known controls and audited source study required')
        known=load(a.known_study/'report.json')
        assert known['result']=='native_error_budget_known_qualified' and known['all_known_qualified']
        for name,digest in known['sources'].items():
            assert sha(repo/name)==sha(a.known_study/'exact_sources'/name)==digest
        native=load(a.source_study/'report.json')
        na=load(a.source_study.parent/'native_audit/report.json')
        assert native['result']=='actual_native_clock_case_measured'
        assert na['verification_passed'] and na['producer_sha256']==sha(a.source_study/'report.json')
        from native_clock_case_v1.binding import bind
        from native_clock_render_v1.geometry import dense_query
        from native_clock_render_v1.filter import taps
        args=native['paths']
        z,prepared,binding=bind(args['case'],args['math_audit'],repo=repo,workspace=a.workspace,
            native_study=args['native_study'],native_audit=args['native_audit'],
            known_study=args['known_study'],known_audit=args['known_audit'])
        r['inputs'].update(binding['inputs'])
        for path in (a.known_study/'report.json',a.source_study/'report.json',
                     a.source_study.parent/'native_audit/report.json'):
            r['inputs'][str(path)]=sha(path)
        raw,fir=prepared['raw_native_target'],prepared['source_FIR_only_target']
        signals=np.column_stack((z['audio'],z['wave']))
        for radius,up in ((32,16),(64,16),(128,16),(128,32)):
            path=a.source_study/('render'+str(up)+'.npz')
            r['inputs'][str(path)]=sha(path)
            assert sha(path)==next(c for c in native['renders'] if c['up']==up)['sha256']
            with np.load(path) as f:
                continuous=f['native'];query=f['query'];kernel=f['taps']
            independent_query,_,_=dense_query(z['source_coordinates'],float(prepared['native_start']),len(raw),up=up,delay=128*up)
            assert np.array_equal(query,independent_query) and np.array_equal(kernel,taps(up))
            dense=reconstruct(signals,query,radius)
            rendered=signal.fftconvolve(dense,kernel[:,None],mode='valid',axes=0)[::up]
            phase,fit_grid=rendered[:,:2],rendered[:,2:]
            arrays,info=analyze(raw,fir,phase,fit_grid,continuous)
            filename='radius'+str(radius)+'_up'+str(up)+'.npz'
            output=a.out/filename
            np.savez_compressed(output,raw=raw,FIR_only=fir,phase_reconstruction=phase,
                fitted_grid_reconstruction=fit_grid,continuous_OSC=continuous,**arrays)
            r['variants'].append(dict(radius=radius,up=up,file=filename,sha256=sha(output),**info))
            save(a.out/'report.json',r)
            print('NATIVE_ERROR_VARIANT',radius,up,'closure',info['closure_max_FS'],flush=True)
        r.update(result='actual_native_error_budget_measured',source=binding['source'],
            source_solver_qualified=native['source_solver_qualified'],
            source_fidelity_qualified=native['source_fidelity_qualified'],
            native16_32_convergence_passed=native['native16_32_convergence_passed'],
            eligible_for_later_source_statistics=native['eligible_for_later_source_statistics'],
            locked_band_power=z['band_power'].tolist(),locked_floor_active=z['floor_active'].tolist(),
            locked_sigma=float(z['sigma']),locked_amplitude=float(z['amplitude']),
            original_source_metrics=load(Path(args['case'])/'report.json')['metrics'],
            original_native_comparisons=native['comparisons'],
            no_refit_or_gate_change_or_source_promotion=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':
    main()
