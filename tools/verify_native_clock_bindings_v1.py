"""Independent frozen native controls/preparation and publication binding audit."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('archive','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    def load(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
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
            if 'file' in c:assert sha(e/folder/c['file'])==c['sha256']
            if 'reference_file' in c:assert sha(e/folder/c['reference_file'])==c['reference_sha256']
    ka,pa=reports['known_audit1'],reports['prepare_audit1']
    assert ka['all_known_qualified'] and len(ka['cases'])==13
    assert pa['all_preparation_qualified'] and len(pa['cases'])==6
    assert ka['producer_sha256']==sha(e/'known1/report.json')
    assert pa['producer_sha256']==sha(e/'prepare1/report.json')
    assert len(reports['known1']['guards'])==10
    assert all(c['all_known_gates_passed'] for c in ka['cases'])
    pure=next(c for c in ka['cases'] if c['label']=='pure_stopband')
    assert pure['native32_reference_NRMSE']>0.003 # retained, attenuation gate has a separate predeclared normalization
    assert not ka['real_fit_or_universal_oversampling_or_C_or_hearing_qualified']
    assert all(not c['actual_fitted_native_render_qualified'] for c in pa['cases'])
    published=load(e/'native_source_band_summary.json');assert published==v['native_source_band_summary']
    for row,c in zip(published,reports['prepare1']['cases']):
        assert row['label']==c['label'] and row['source_cutoff_hz']==c['source_cutoff_hz']==14000.
        raw=sum(row['raw_14to24k_mean_power_FS2'])/row['raw_total_mean_power_FS2']
        assert abs(raw-row['raw_14to24k_fraction'])<1e-22 and raw<1e-8
        assert row['FIR_only_band_power_change_dB']==c['source_FIR_only_signed_changes']['broad']['power_change_dB']
        assert max(abs(x) for x in row['FIR_only_band_power_change_dB'][3])<4.1e-7
    for name,digest in v['current_source_sha256'].items():assert sha(a.archive/'source'/name)==digest
    assert v['C_H_exact']==670 and v['voice_parameters_exact']==82 and v['F2_files_exact']==3
    assert not v['actual_fitted_native_render_qualified']
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    for original in v['original_input_archive_locations']:
        if '/waveform_file_real_v1/real1/' in original.replace('\\','/'):
            assert Path(original).name=='run_spec.json'
    r=dict(result='independent_native_clock_bindings_verified',all_archive_bindings_verified=True,
        checked_bindings=count,known_cases=13,actual_preparations=6,publication_arithmetic_verified=True,
        no_live_fit_payload_or_actual_native_promotion=True,manifest_sha256=sha(a.archive/'manifest.json'),
        auditor_sha256=sha(__file__))
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(r,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
