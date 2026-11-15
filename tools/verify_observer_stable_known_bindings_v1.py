"""Read-only frozen stable-known sources, two-parent inputs and executed bindings."""
import argparse, hashlib, json
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
    assert not v['live_full_output_included'] and not (e/'full1').exists()
    folders=set(v['selected_terminal_evidence_directories'])
    assert {p.name for p in e.iterdir() if p.is_dir()}==folders
    manifests={}
    for name,digest in v['upstream_manifests_sha256'].items():
        path=a.archive/'inputs/upstream'/name/'manifest.json'
        assert sha(path)==digest
        manifests[name]={r['path']:r['sha256'] for r in read(path)['files']}
    sources=inputs=captures=executed=0
    def bound(original,digest):
        nonlocal inputs
        target=v['original_input_archive_locations'][original]
        assert sha(a.archive/target)==digest
        parts=Path(target).parts
        if parts[0]=='inputs':
            assert parts[1]=='upstream'
            assert manifests[parts[2]][Path(*parts[3:]).as_posix()]==digest
        else:
            assert parts[0]=='evidence' and parts[1] in folders
        inputs+=1
    for folder in ('controls1','known1','known_mapped1'):
        r=read(e/folder/'report.json')
        for name,digest in r['sources'].items():
            assert sha(e/folder/'exact_sources'/name)==sha(a.archive/'source'/name)==digest
            sources+=1
        for original,digest in r.get('inputs',{}).items(): bound(original,digest)
        for c in r['cases']:
            assert sha(e/folder/c['file'])==c['sha256']
            captures+=1
        if folder!='controls1': assert r['all_qualified'] and len(r['cases'])==12
    for folder,producer,script in (('controls_audit1','controls1','audit_observer_stable_controls_v1.py'),
            ('known_audit1','known1','audit_observer_stable_known_v1.py'),
            ('known_mapped_audit1','known_mapped1','audit_observer_stable_known_v1.py')):
        r=read(e/folder/'report.json')
        assert r['result'].startswith('independent_') and r['result'].endswith('_passed')
        assert sha(e/producer/'report.json')==r['producer_sha256']
        assert sha(e/folder/'executed_audit.py')==sha(a.archive/'source/tools'/script)==r['auditor_sha256']
        executed+=1
        for j,(name,digest) in enumerate(r.get('oracles_sha256',{}).items()):
            assert sha(e/folder/f'executed_oracle_{j}.py')==sha(a.archive/'source'/name)==digest
            executed+=1
    storage=read(e/'storage_audit1/report.json')
    assert storage['result']=='independent_observer_stable_storage_passed'
    assert storage['RAM_report_sha256']==sha(e/'known1/report.json')
    assert storage['mapped_report_sha256']==sha(e/'known_mapped1/report.json')
    assert storage['auditor_sha256']==sha(e/'storage_audit1/executed_audit.py')==sha(a.archive/'source/tools/audit_observer_stable_storage_v1.py')
    assert len(storage['cases'])==12 and all(len(c['arrays_sha256'])==18 for c in storage['cases'])
    raw=0
    for c in storage['cases']:
        for name,digest in c['raw_basis_files_sha256'].items():
            assert sha(e/'known_mapped1'/name)==digest
            raw+=1
    assert raw==24
    pub=read(e/'known_review1/report.json')
    assert sha(e/'known_review1/executed_publication.py')==pub['publisher_sha256']==sha(a.archive/'source/tools/publish_observer_stable_known_v1.py')
    assert sha(e/'known_review1/figure_inputs.json')==pub['figure_inputs_sha256']
    for name,digest in pub['inputs'].items(): bound(name,digest)
    assert all(sha(e/'known_review1'/name)==digest for name,digest in pub['images'].items())
    audit=read(e/'known_review1/metrics_verification.json')
    assert audit['result']=='independent_observer_stable_known_publication_passed'
    assert audit['producer_sha256']==sha(e/'known_review1/report.json')
    assert audit['auditor_sha256']==sha(e/'known_review1/executed_metrics_audit.py')==sha(a.archive/'source/tools/audit_observer_stable_known_review_v1.py')
    visual=read(e/'known_review1/visual_review.json')
    assert visual['accepted_for_publication'] and visual['scientific_figures_individually_viewed']==2
    assert visual['images_sha256']==pub['images']
    assert pub['summary']==v['results']==audit['summary']
    assert v['results']['bitwise_equal_old_fitted']==v['results']['stable_qualified']==12
    old=[read(a.archive/path) for name,path in v['original_input_archive_locations'].items() if name.endswith('reorth_known_audit1\\report.json')]
    assert len(old)==1
    assert sum(c['qualified'] for c in old[0]['cases'])==4
    assert sum(c['kind']=='Hann' and c['stopping_code']==7 and not c['qualified'] for c in old[0]['cases'])==8
    result=dict(result='independent_observer_stable_known_input_executed_capture_bindings_verified',
        producer_source_bindings=sources,original_input_bindings=inputs,capture_bindings=captures,
        executed_auditor_oracle_bindings=executed,trimmed_raw_basis_bindings=raw,
        upstream_archives=sorted(manifests),old_eight_failures_retained=True,live_full_output_excluded=True,
        scientific_figures_verified=2,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':
    main()
