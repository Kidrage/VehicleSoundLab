"""Bind full-band/modal-budget research to executed known, source and audit bytes."""
import argparse
from pathlib import Path
import shutil

from research_archive_v1 import load,save,sha,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output
    repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/event_spectral_budget_v1')
    stages=('known1','fit1','audit1','components1')
    reports={name:load(root/name/'report.json') for name in stages}
    assert all(r['result']=='passed' for r in reports.values())
    assert reports['fit1']['qualified_cases']==reports['audit1']['qualified_cases']==[]
    for stage in ('audit1','components1'):
        assert reports[stage]['reviewed_report_sha256']==sha(root/'fit1/report.json')
    for path,digest in reports['audit1']['waveforms'].items():assert sha(Path(path))==digest
    assert len(reports['audit1']['waveforms'])==32
    for path in (repo/'tools/event_spectral_source').glob('*.py'):
        for stage in ('known1','fit1'):
            assert sha(path)==sha(root/stage/'exact_sources'/path.relative_to(repo))
    runtime=load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/selection1/runtime.json'))
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    assert reports['known1']['infeasible_stop']['phaseII_executed'] is False
    catch=next(c for c in reports['fit1']['cases'] if c['kind']=='catch')
    assert not catch['fitting']['phaseI']['feasible'] and not catch['fitting']['phaseII_executed']
    component=next(c for c in reports['components1']['cases'] if c['kind']=='crank')
    assert component['mean_upper_bound_modal_to_target'][2]<.06
    out.mkdir(parents=True,exist_ok=False)
    sources=[repo/'AGENTS.md',repo/'handoff/启动全频预算与可行性检查V1.md',
        repo/'research/event_spectral_budget_v1_plan.json',repo/'research/event_modal_capacity_next_v1_plan.json',
        *sorted((repo/'tools/event_spectral_source').glob('*.*')),
        *[repo/'tools'/name for name in ('verify_event_spectral_budget_v1.py','refine_event_spectral_budget_v1.py',
            'audit_event_spectral_budget_v1.py','inspect_event_spectral_components_v1.py',
            'finalize_event_spectral_budget_v1.py','audit_startup_contour_ensemble_v1.py',
            'refine_startup_band_texture_v1.py')]]
    bindings={}
    for p in sources:
        name=p.relative_to(repo);dest=out/'final_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        bindings[name.as_posix()]=sha(dest);assert sha(p)==sha(dest)
    summary=dict(result='passed',qualified_cases=[],runtime_integrated=False,
        final_sources=bindings,terminal_reports={str(root/name/'report.json'):sha(root/name/'report.json') for name in stages},
        independently_audited_waveforms=reports['audit1']['waveforms'],original_C_files=16,new_Python_files=16,
        original_qualification_gates_unchanged=True,known_feasible_and_infeasible_paths_verified=True,
        known_and_crank_phaseII_iteration_limits_preserved=True,catch_stopped_before_phaseII=True,
        real_training_shape_improvement={c['kind']:c['relative_legacy_shape_improvement'] for c in reports['fit1']['cases']},
        crank_modal_mid_actual_fraction=component['mean_modal_to_target'][2],
        crank_modal_mid_conservative_mean_upper_fraction=component['mean_upper_bound_modal_to_target'][2],
        capacity_bound_scope='Current source modal coefficients,0..8 existing contour gains,four fixed training realizations; not a limit of OSC synthesis',
        component_known_vertex_and_balanced_sign_controls=reports['components1']['known_vertex_and_balanced_sign_controls'],
        no_candidate_promoted=True,runtime_voice_files_unchanged=459,figure_viewed='fit1/temporal.png',
        no_active_experiment_process=True,delivery_root=str(out),goal_complete=False,timbre_accepted=False)
    save(repo/'research/event_spectral_budget_v1_verification.json',summary)
    save(out/'verification.json',summary)
    entries=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
             for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json',dict(files=entries,file_count=len(entries),bytes=sum(e['bytes'] for e in entries)))
    verify(out)
    print('full-budget modules, known/source/audit and modal-capacity evidence bound; goal active',flush=True)


if __name__=='__main__':main()
