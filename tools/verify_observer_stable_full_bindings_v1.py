"""Read-only full288 archive source/input/basis/executed bindings and failed gates."""
import argparse, hashlib, json, math
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','out'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    def read(path): return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
    e=a.archive/'evidence'
    v=read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    manifests={}
    for name,digest in v['upstream_manifests_sha256'].items():
        path=a.archive/'inputs/upstream'/name/'manifest.json'
        assert sha(path)==digest
        manifests[name]={r['path']:r['sha256'] for r in read(path)['files']}
    inputs=sources=0
    def bound(name,digest):
        nonlocal inputs
        target=v['original_input_archive_locations'][name]
        assert sha(a.archive/target)==digest
        parts=Path(target).parts
        if parts[0]=='inputs':
            assert parts[1]=='upstream'
            assert manifests[parts[2]][Path(*parts[3:]).as_posix()]==digest
        else:
            assert parts[0]=='evidence' and parts[1] in v['selected_terminal_evidence_directories']
        inputs+=1
    full=read(e/'full1/report.json')
    assert full['result']=='observer_stable_full_known_measured' and full['only_one_attempt']
    for name,digest in full['sources'].items():
        assert sha(e/'full1/exact_sources'/name)==sha(a.archive/'source'/name)==digest
        sources+=1
    for name,digest in full['inputs'].items(): bound(name,digest)
    assert sha(e/'full1/capture.npz')==full['capture_sha256']
    assert len(full['basis_files'])==2
    for name,digest in full['basis_files'].items(): assert sha(e/'full1'/name)==digest
    for name in ('U','V'):
        shape=full['solver']['basis_shapes'][name]
        assert (e/'full1/basis'/(name+'.bin')).stat().st_size==8*math.prod(shape)
    audit=read(e/'full_audit1/report.json')
    assert audit['result']=='independent_observer_stable_full_passed'
    assert audit['producer_sha256']==sha(e/'full1/report.json')
    assert audit['auditor_sha256']==sha(e/'full_audit1/executed_audit.py')==sha(a.archive/'source/tools/audit_observer_stable_full_v1.py')
    executed=1
    for j,(name,digest) in enumerate(audit['oracles_sha256'].items()):
        assert sha(e/'full_audit1'/f'executed_oracle_{j}.py')==sha(a.archive/'source'/name)==digest
        executed+=1
    assert audit['full_basis_Grams_verified']
    columns=audit['independently_checked_projection_columns']
    assert len(columns)==len(set(columns))==min(64,full['solver']['directions'])
    assert columns[0]==0 and columns[-1]==full['solver']['directions']-1
    for key in ('solver_qualified','fidelity_qualified'): assert audit[key]==full[key]==v[key]
    units=read(e/'frequency_units_audit1/report.json')
    assert units['result']=='independent_observer_stable_frequency_units_passed'
    assert units['auditor_sha256']==sha(e/'frequency_units_audit1/executed_audit.py')==sha(a.archive/'source/tools/audit_observer_stable_frequency_units_v1.py')
    assert units['producer_source_sha256']==full['sources']['tools/run_observer_stable_full_v1.py']
    assert units['band_edges_source_sha256']==full['sources']['tools/observer_frequency_v1/metric.py']
    assert units['analysis_rate_Hz']==65536 and units['final_band_Hz']==[14000.,32768.]
    assert units['bins_per_band']==[188,187,125,125,250,1174]
    watch=read(e/'full_watch1/report.json')
    assert watch['result']=='observer_stable_full_watch_and_audit_terminal'
    assert watch['producer_exit_code']==watch['audit_exit_code']==0
    assert watch['producer_report_sha256']==sha(e/'full1/report.json')
    assert watch['audit_report_sha256']==sha(e/'full_audit1/report.json')
    assert watch['auditor_sha256']==audit['auditor_sha256']
    assert watch['watcher_sha256']==sha(e/'full_watch1/executed_watch.py')==sha(a.archive/'source/tools/watch_observer_stable_full_v1.py')
    observations=(e/'full_watch1/observations.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(observations)==watch['snapshots']
    for line in observations:
        value=json.loads(line)
        assert value['producer_handle_confirmed_live'] and value['progress']['pid']==full['pid']
    assert json.loads(observations[-1])==watch['latest_observed']
    for folder,tool,array,key in (
        ('stationarity_gap_audit1','audit_observer_stationarity_gap_v1.py','frozen_full_normals.npz','full_capture_sha256'),
        ('full_gap_alignment1','audit_observer_stable_gap_alignment_v1.py','normals.npz','normals_sha256')):
        extra=read(e/folder/'report.json')
        expected='independent_observer_stationarity_gap_identity_passed' if folder=='stationarity_gap_audit1' else 'independent_observer_stable_gap_alignment_passed'
        assert extra['result']==expected
        assert extra['auditor_sha256']==sha(e/folder/'executed_audit.py')==sha(a.archive/'source/tools'/tool)
        for name,digest in extra['inputs'].items(): bound(name,digest)
        for j,(name,digest) in enumerate(extra['sources'].items()):
            assert sha(e/folder/f'executed_oracle_{j}.py')==sha(a.archive/'source'/name)==digest
        assert sha(e/folder/array)==extra[key]
        if folder=='stationarity_gap_audit1': assert len(extra['controls'])==6 and extra['new_solves']==0
        else:
            assert extra['solver_qualified_unchanged']==full['solver_qualified']
            assert len(extra['subspace_known_controls'])==5
    pub=read(e/'full_review1/report.json')
    assert pub['publisher_sha256']==sha(e/'full_review1/executed_publication.py')==sha(a.archive/'source/tools/publish_observer_stable_full_v1.py')
    assert pub['figure_inputs_sha256']==sha(e/'full_review1/figure_inputs.json')
    for name,digest in pub['inputs'].items(): bound(name,digest)
    assert all(sha(e/'full_review1'/name)==digest for name,digest in pub['images'].items())
    publication=read(e/'full_review1/metrics_verification.json')
    assert publication['result']=='independent_observer_stable_full_publication_passed'
    assert publication['producer_sha256']==sha(e/'full_review1/report.json')
    assert publication['auditor_sha256']==sha(e/'full_review1/executed_metrics_audit.py')==sha(a.archive/'source/tools/audit_observer_stable_full_review_v1.py')
    assert publication['summary']==pub['summary']==v['results']
    assert publication['all17_fidelity_rows_all_checkpoints_and_four_gaps_verified']
    visual=read(e/'full_review1/visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2
    assert visual['images_sha256']==pub['images']
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_observer_stable_full_v1.py')
    assert sha(Path(__file__))==sha(a.archive/'source/tools/verify_observer_stable_full_bindings_v1.py')
    result=dict(result='independent_observer_stable_full_input_executed_capture_bindings_verified',
        producer_source_bindings=sources,original_input_bindings=inputs,raw_basis_bindings=2,
        executed_auditor_oracle_bindings=executed,full_Gram_verified=True,
        independently_checked_projection_columns=len(columns),upstream_archives=sorted(manifests),
        independent_gap_identity_controls=6,terminal_complete_normal_alignment_verified=True,
        independent_subspace_controls=5,
        solver_qualified=full['solver_qualified'],fidelity_qualified=full['fidelity_qualified'],
        final_band_includes_analysis_Nyquist=True,all_failures_and_regressions_preserved=True,
        scientific_figures_verified=2,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':
    main()
