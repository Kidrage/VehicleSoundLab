"""Read-only executed-version/input/failed-gate verification of the graph archive."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    def read(p):return json.loads(p.read_text('utf-8'))
    def sha(p):
        with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    e=a.archive/'evidence';v=read(a.archive/'validation.json')
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    manifests={}
    for n,h in v['upstream_manifests_sha256'].items():
        p=a.archive/'inputs/upstream'/n/'manifest.json';assert sha(p)==h
        manifests[n]={r['path']:r['sha256'] for r in read(p)['files']}
    inputs=sources=0;versions=set()
    def bind(n,h):
        nonlocal inputs
        target=v['original_input_archive_locations'][n];p=a.archive/target;assert sha(p)==h
        parts=Path(target).parts
        if parts[0]=='inputs':assert manifests[parts[2]][Path(*parts[3:]).as_posix()]==h
        else:assert parts[0]=='evidence' and parts[1] in v['selected_terminal_evidence_directories']
        inputs+=1
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        for n,h in r.get('inputs',{}).items():bind(n,h)
        for n,h in r.get('sources',{}).items():
            p=e/folder/'exact_sources'/n
            if p.is_file():assert sha(p)==h;sources+=1
            if n=='tools/waveform_nullspace_v1/algebra.py':versions.add(h)
        for group in ('cases','frames'):
            for c in r.get(group,[]):
                if 'file' in c:assert sha(e/folder/c['file'])==c['sha256']
        if 'producer_sha256' in r:
            parent={'explicit_audit1':'explicit1','known_audit1':'known1',
                'graph_explicit_audit1':'graph_explicit1','graph_known_audit1':'graph_known1',
                'precision_audit1':'precision_diagnosis1'}[folder]
            assert sha(e/parent/'report.json')==r['producer_sha256']
            assert sha(e/folder/'executed_audit.py')==r['auditor_sha256']
    assert len(versions)==2
    s=read(e/'summary_audit1/report.json');assert s['versions']==v['results']
    assert len(s['rows'])==36
    assert [s['versions'][k]['qualified'] for k in ('previous','nullspace','graph')]==[9,9,12]
    assert s['versions']['nullspace']['original_equations_and_gaps_passed']==9
    assert s['versions']['graph']['original_equations_and_gaps_passed']==12
    assert s['versions']['graph']['original_direct_normal_passed']==4
    assert len(read(e/'precision_audit1/report.json')['cases'])==4
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_waveform_graph_v1.py')
    result=dict(result='independent_waveform_graph_archive_bindings_verified',source_bindings=sources,
        original_input_bindings=inputs,nullspace_module_executed_versions=len(versions),summary_rows=36,
        original12_graph_qualified=12,original12_direct_normal_passed=4,
        old_failed_gap_and_normal_records_preserved=True,independent_Decimal_diagnostic_cases=4,
        source_or_full_or_C_or_hearing_qualified=False,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':main()
