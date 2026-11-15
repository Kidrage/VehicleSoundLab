"""Independent static archive bindings; no live-fit files or producer imports."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('archive','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    def load(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    v=load(a.archive/'validation.json');e=a.archive/'evidence';count=0
    def bound(name,digest):
        nonlocal count
        path=a.archive/v['original_input_archive_locations'][name]
        assert path.resolve().is_relative_to(a.archive.resolve()) and sha(path)==digest
        count+=1
    reports={name:load(e/name/'report.json') for name in v['selected_terminal_evidence_directories']}
    for folder,r in reports.items():
        for name,digest in r.get('inputs',{}).items():bound(name,digest)
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest==v['executed_source_versions'][name][folder]
        for c in r.get('cases',[]):
            if 'file' in c:
                path=e/folder/c['file'];assert sha(path)==c.get('capture_sha256',c.get('sha256'))
            if 'report' in c:assert sha(e/folder/c['report'])==c['report_sha256']
    def factors(value):
        if isinstance(value,dict):
            if {'path','shape','file_bytes','sha256'}<=value.keys():
                bound(value['path'],value['sha256'])
                assert value['closed'] and not value['mapped']
                assert value['file_bytes']==8*value['shape'][0]*value['shape'][1]
            for child in value.values():factors(child)
        elif isinstance(value,list):
            for child in value:factors(child)
    for case in reports['known1']['cases']:factors(load(e/'known1'/case['report']))
    assert reports['known1']['all_qualified'] and len(reports['known1']['cases'])==4
    assert reports['known_audit1']['producer_sha256']==sha(e/'known1/report.json')
    assert reports['known_audit1']['all_qualified'] and len(reports['known_audit1']['cases'])==4
    for name in ('generic_audit1','generic_audit2'):
        assert reports[name]['all_qualified'] and len(reports[name]['cases'])==3
        for c in reports[name]['cases']:
            assert c['producer_sha256']==sha(e/'known1'/c['label']/'report.json')
            assert c['solver_qualified'] and c['fidelity_qualified']
    prep,pa=reports['prepare1'],reports['prepare_audit1']
    assert pa['producer_sha256']==sha(e/'prepare1/report.json') and pa['all_qualified'] and len(pa['cases'])==6
    assert prep['all_resources_passed'] and prep['retained_six_disk_passed'] and prep['no_inverse_fit']
    for c in prep['cases']:
        assert c['orders']==288 and c['frames']-c['target_frames']==4096
        assert c['resources']['graph_transpose_three_owned_panels_counted']
        bound(c['context_file'],prep['inputs'][c['context_file']])
        for path in c['original_files'].values():bound(path,prep['inputs'][path])
    assert set(x.name for x in e.iterdir() if x.is_dir())==set(v['selected_terminal_evidence_directories'])
    for name,digest in v['current_source_sha256'].items():assert sha(a.archive/'source'/name)==digest
    assert v['C_H_exact']==670 and v['voice_parameters_exact']==82 and v['F2_files_exact']==3
    r=dict(result='independent_waveform_file_real_adapter_bindings_verified',all_qualified=True,
        checked_bindings=count,known_controls=4,real_preparations=6,no_live_fit_payload_or_completion_claim=True,
        manifest_sha256=sha(a.archive/'manifest.json'),auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(r,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
