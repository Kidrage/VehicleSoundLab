"""Bind actual normalized-projection runs, retained audit failure and final sources."""
import argparse
from pathlib import Path
import shutil

from research_archive_v1 import load,save,sha,verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output
    out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/event_modal_projection_v1')
    stages=['known1','source1','audit1','known2','audit2']
    reports={name:load(root/name/'report.json') for name in stages}
    assert all(reports[name]['result']=='passed' for name in ['known1','source1','known2','audit2'])
    assert reports['audit1']['result']=='failed' and '2.7274840719293536e-10' in reports['audit1']['error']
    first,second=(reports[name]['source_bindings'] for name in ['known1','known2'])
    changed=[name for name in first if first[name]!=second[name]]
    assert changed==['tools/audit_event_modal_projection_v1.py']
    assert all(sha(repo/name)==digest for name,digest in second.items())
    real=reports['source1']
    for name,digest in real['source_bindings'].items():
        assert sha(root/'source1/exact_sources'/name)==digest
        if name not in changed:assert sha(repo/name)==digest
    runtime=load(root.parent/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
    assert len(reports['audit2']['cases'])==20
    assert reports['audit2']['input_report_sha256']==sha(root/'source1/report.json')
    for row in reports['audit2']['cases']:
        folder=root/'source1'/row['kind']
        for field,label in [('projection_sha256','projection'),('remainder_sha256','remainder')]:
            assert row[field]==sha(folder/(row['model']+'-'+row['split']+'-'+label+'.wav'))
    summaries=[]
    for case in real['cases']:
        best=case['models'][-1]
        assert best['id']=='quad9'
        assert all(m['interpolation']['energy']['withheld']['explained_SSE_fraction']<0 for m in case['models'])
        summaries.append(dict(kind=case['kind'],full_explained_waveform_SSE_fraction=best['full']['energy']['all']['explained_SSE_fraction'],
            withheld10ms_explained_waveform_SSE_fraction=best['interpolation']['energy']['withheld']['explained_SSE_fraction'],
            middle_signed_budget=best['full']['bands'][2],maximum_columns_per_channel=best['full']['fitting']['columns']))
    sources=set(second)|{
        'AGENTS.md','handoff/启动振子表达能力核查V1.md',
        'research/event_modal_projection_followup_v1_plan.json',
        'tools/inspect_event_modal_projection_v1.py','tools/finalize_event_modal_projection_v1.py',
        'tools/research_archive_v1.py','tools/event_authoring/audio.py','tools/event_authoring/contract.py'}
    bindings={}
    for name in sorted(sources):
        dest=out/'final_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,dest)
        bindings[name]=sha(dest)
        assert bindings[name]==sha(repo/name)
    summary=dict(result='passed',goal_complete=False,timbre_accepted=False,runtime_integrated=False,
        qualified_cases=[],representation_capacity_only=True,cases=summaries,
        terminal_reports={str(root/name/'report.json'):sha(root/name/'report.json') for name in stages},
        corrected_audit_implementation_only=changed,failed_audit_retained=True,
        original_direct_gate_FS=2e-10,source_fit_and_gates_unchanged=True,
        independently_audited_projections=20,independently_audited_remainders=20,
        maximum_coefficient_realization_error_FS=max(r['coefficient_direct_error_FS'] for r in reports['audit2']['cases']),
        maximum_spectral_balance_error_FS2=max(r['spectral_balance_error_FS2'] for r in reports['audit2']['cases']),
        runtime_voice_files_unchanged=459,old_random_heldouts_not_used=True,
        final_sources=bindings,figure_viewed='source1/capacity.png',delivery_root=str(out),
        limitation='Conditional fixed-frequency sparse-envelope acoustic capacity and same-event interpolation. Not physical source fractions, a stochastic timbre gate or a bound on general OSC synthesis. No new reusable voice.')
    save(repo/'research/event_modal_projection_v1_verification.json',summary)
    save(out/'verification.json',summary)
    entries=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
             for p in sorted(out.rglob('*')) if p.is_file()]
    save(out/'manifest.json',dict(files=entries,file_count=len(entries),bytes=sum(e['bytes'] for e in entries)))
    verify(out)
    print('known/source/independent audit bound; retained failure and runtime identity verified; goal active',flush=True)


if __name__=='__main__':main()
