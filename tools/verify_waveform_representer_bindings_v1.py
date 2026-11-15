"""Verify frozen executed variants and original-parent input bindings read-only."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a = p.parse_args()
    def read(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    v=read(a.archive/'validation.json');e=a.archive/'evidence'
    assert {p.name for p in e.iterdir() if p.is_dir()} == set(v['selected_terminal_evidence_directories'])
    manifests={}
    for name,expected in v['upstream_manifests_sha256'].items():
        path=a.archive/'inputs/upstream'/name/'manifest.json'
        assert sha(path)==expected
        manifests[name]={r['path']:r['sha256'] for r in read(path)['files']}
    input_count=source_count=0;variants={}
    def bound(name,expected):
        nonlocal input_count
        path=v['original_input_archive_locations'][name]
        assert sha(a.archive/path)==expected
        parts=Path(path).parts
        if parts[0]=='inputs':
            assert parts[1]=='upstream' and manifests[parts[2]][Path(*parts[3:]).as_posix()]==expected
        else:assert parts[0]=='evidence' and parts[1] in v['selected_terminal_evidence_directories']
        input_count+=1
    for number in (1,2):
        for name in ('explicit','known'):
            folder=e/f'{name}{number}';r=read(folder/'report.json')
            assert r['material_read'] is False
            for file,expected in r['sources'].items():
                assert sha(folder/'exact_sources'/file)==expected
                variants.setdefault(file,set()).add(expected);source_count+=1
            for file,expected in r.get('inputs',{}).items():bound(file,expected)
            for group in ('cases','frames'):
                for case in r.get(group,[]):assert sha(folder/case['file'])==case['sha256']
            audit_folder=e/f'{name}_audit{number}';audit=read(audit_folder/'report.json')
            assert audit['producer_sha256']==sha(folder/'report.json')
            assert audit['auditor_sha256']==sha(audit_folder/'executed_audit.py')
            for index,(file,expected) in enumerate(audit.get('oracles_sha256',{}).items()):
                assert sha(audit_folder/f'executed_oracle_{index}.py')==expected
        assert len(read(e/f'explicit{number}/report.json')['cases'])==7
        assert len(read(e/f'explicit{number}/report.json')['frames'])==4
        assert len(read(e/f'known{number}/report.json')['cases'])==12
    assert len(variants['tools/waveform_representer_v1/algebra.py'])==2
    assert len(variants['tools/run_waveform_representer_known_v1.py'])==2
    pub=read(e/'review1/report.json');pa=read(e/'publication_audit1/report.json')
    assert pub['summary']==pa['summary']==v['results']
    assert pub['publisher_sha256']==sha(e/'review1/executed_publication.py')
    assert pub['figure_inputs_sha256']==sha(e/'review1/figure_inputs.json')
    for file,expected in pub['inputs'].items():bound(file,expected)
    for file,expected in pub['images'].items():assert sha(e/'review1'/file)==expected
    assert pa['producer_publication_sha256']==sha(e/'review1/report.json')
    assert pa['auditor_sha256']==sha(e/'publication_audit1/executed_audit.py')
    assert pa['plotted_rows']==24 and pa['summary']['after_passes']==9 and pa['summary']['before_passes']==4
    assert len(pa['summary']['failed_labels'])==3
    result=dict(result='independent_waveform_representer_archive_bindings_verified',
        source_bindings=source_count,original_input_bindings=input_count,
        distinct_algebra_versions=2,distinct_original12_runner_versions=2,
        original12_qualified=9,original12_failures=3,publication_rows=24,
        previous13GB_basis_not_copied=not any(p.suffix=='.bin' for p in a.archive.rglob('*')),
        auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(result,flush=True)


if __name__=='__main__':main()
