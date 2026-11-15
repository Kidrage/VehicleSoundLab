"""Independent archival input/source/failure/numeric publication binding audit."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    def read(path):return json.loads(path.read_text(encoding='utf-8'))
    def sha(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    v=read(a.archive/'validation.json');e=a.archive/'evidence'
    assert {p.name for p in e.iterdir() if p.is_dir()}==set(v['selected_terminal_evidence_directories'])
    parents={}
    for name,digest in v['upstream_manifests_sha256'].items():
        path=a.archive/f'inputs/upstream/{name}/manifest.json';assert sha(path)==digest
        parents[name]={row['path']:row['sha256'] for row in read(path)['files']}
    sources=inputs=files=0
    for folder in v['selected_terminal_evidence_directories']:
        r=read(e/folder/'report.json')
        for name,digest in r.get('inputs',{}).items():
            target=v['original_input_archive_locations'][name];assert sha(a.archive/target)==digest
            parts=Path(target).parts
            if parts[:2]==('inputs','upstream'):
                leaf=Path(*parts[3:]).as_posix()
                assert (v['upstream_manifests_sha256'][parts[2]] if leaf=='manifest.json' else parents[parts[2]][leaf])==digest
            inputs+=1
        for name,digest in r.get('sources',{}).items():
            assert sha(e/folder/'exact_sources'/name)==digest;sources+=1
        for kind in ('cases','rejections'):
            for case in r.get(kind,[]):
                if 'file' in case:assert sha(e/folder/case['file'])==case['sha256'];files+=1
        if 'auditor_sha256' in r:assert sha(e/folder/'executed_audit.py')==r['auditor_sha256']
    def report(n):return read(e/n/'report.json')
    known,known_audit,failed,real,real_audit=[report(n) for n in ('known1','known_audit2','known_audit1','real1','real_audit1')]
    assert known['all_qualified'] and known_audit['all_qualified'] and real['all_qualified'] and real_audit['all_qualified']
    assert known_audit['producer_sha256']==sha(e/'known1/report.json')
    assert real_audit['producer_sha256']==sha(e/'real1/report.json')
    assert known_audit['pass_count']==v['known_positive_count']==8
    assert len(known['rejections'])==v['known_rejections']==7
    assert all(x['qualified'] for x in known['rejections'])
    assert failed['result']=='failed' and 'coarse_audio' in failed['error']
    assert sha(e/'known_audit1/executed_audit.py')!=sha(e/'known_audit2/executed_audit.py')
    assert known_audit['cases']==v['known_cases'] and real_audit['cases']==v['real_cases']
    assert max(c['known_cycle_std'] for c in known_audit['cases'])==v['known_phase_cycle_std_max']<.002
    assert max(c['analytic_wave_NRMSE'] for c in known_audit['cases'])==v['known_wave_NRMSE_max']<.005
    assert all(c['minimum_heldout_coherence']>.99 for c in known_audit['cases'])
    assert real_audit['pass_count']==v['real_count']==6
    assert min(c['minimum_heldout_coherence'] for c in real_audit['cases'])==v['real_minimum_heldout_coherence']>.8
    assert max(c['direct_FIR_and_polyphase_render_max_error_FS'] for c in real_audit['cases'])==v['real_direct_render_max_error_FS']<2e-12
    comparison=[]
    for c in real['cases']:
        assert c['info']['original_positions_bitwise_exact'] and c['info']['original_audio_bitwise_exact']
        assert c['info']['margin_samples_each_side']==2048
        assert c['info']['extended_frames']==c['info']['original_frames']+4096
        assert c['info']['no_phase_extrapolation'] and c['info']['reference_order']==5
        # Each external original binding must name the exact independently
        # archived source, not merely a matching label or a manifest summary.
        for original in c['original_bindings'].values():assert original in v['original_input_archive_locations']
        for order,regions in c['heldout'].items():
            for region,values in regions.items():
                for channel in (0,1):
                    before=c['original_heldout'][order][channel];after=values['coherence'][channel]
                    comparison.append(dict(label=c['label'],heldout_order=int(order),channel=channel,region=region,
                        original_target_coherence=before,context_region_coherence=after,
                        signed_change=after-before,regression=after<before))
    assert len(comparison)==96 and comparison==v['all96_signed_comparison_rows']
    assert v['real_two_cycle_each_side_context_qualified'] and v['original_audio_coordinates_and_scales_bitwise_exact']
    assert not v['global_clock_or_physical_RPM_or_load_or_AM_PM_identification']
    assert v['memory_preflight_still_required'] and v['no_large_real_inverse_or_new_sustained_sound_or_C_or_hearing_qualification']
    assert not v['runtime_default_driver_owned_take_room_changed'] and v['full_goal']=='active'
    assert sha(e/'executed_package.py')==sha(a.archive/'source/tools/package_recorded_phase_context_v1.py')
    r=dict(result='independent_recorded_phase_context_archive_bindings_verified',
        source_bindings=sources,input_bindings=inputs,case_file_bindings=files,
        all96_signed_comparison_rows_verified=True,failed_first_auditor_retained=True,
        all_six_original_contexts_bound=True,no_runtime_promotion=True,auditor_sha256=sha(Path(__file__)))
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');print(r,flush=True)


if __name__=='__main__':main()
