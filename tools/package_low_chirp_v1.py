"""Freeze the local-chirp observations, failure to persist, and mono-noise counterexample."""
import argparse,platform,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/low_chirp_v1'
evidence=a.workspace/'references/analysis/low_chirp_v1';old=a.workspace/'baselines/idle_drive_v1'
c=load(old/'C_files_sha256.json');voices=load(old/'voice_files_sha256.json')
assert len(c)==569 and len(voices)==67
assert all(sha(repo/name)==digest for name,digest in {**c,**voices}.items())
subprocess.run(['git','diff','--exit-code','HEAD','--','modules','src','experiments','voices','CMakeLists.txt','tools/line_motion_v1'],cwd=repo,check=True,capture_output=True)
if a.stage=='freeze':
    observation=load(evidence/'observe1/report.json');noise=load(evidence/'noise1/report.json')
    audit=load(evidence/'audit2/report.json');publication=load(evidence/'review1/report.json')
    assert observation['result']=='native_independent_low_chirps_and_conservative_tracks_observed'
    assert observation['controls']['passed'] and not observation['holdout_read']
    assert [(r['windows'],r['successful_windows'],r['candidates'],r['eligible']) for r in observation['observations']]==[(7,5,129,61),(11,8,241,86)]
    assert all(r['moving_tracks']==r['stationary_tracks']==0 for r in observation['observations'])
    assert noise['result']=='unchanged_rule_checked_on_mono_noise'
    assert noise['original_independent_stereo_eligible']==0 and noise['mono_eligible']==1
    assert audit['result']=='native_models_eligibility_and_every_link_rebuilt' and audit['windows']==18
    assert audit['mono_noise_audit']['mono_eligible']==1 and not audit['optimizer_rerun']
    assert load(evidence/'audit1/report.json')['result']=='native_models_eligibility_and_every_link_rebuilt'
    assert publication['result']=='all_known_and_real_tracks_plotted' and not publication['holdout_read']
    assert sha(repo/'tools/audit_low_chirp_v1.py')==sha(evidence/'audit2/executed_audit.py')
    assert sha(repo/'tools/publish_low_chirp_v1.py')==sha(evidence/'review1/executed_publish.py')
    sources={'tools/package_low_chirp_v1.py','tools/audit_low_chirp_v1.py','tools/publish_low_chirp_v1.py',
        'tools/research_archive_v1.py','research/低频局部声线与持续性V1.md','AGENTS.md',
        'handoff/算法说明.md','handoff/开发留痕.md','handoff/研究续接.md',
        'tools/line_motion_v1/__init__.py','tools/line_motion_v1/moments.py'}
    for folder,report in [('observe1',observation),('noise1',noise)]:
        for name,digest in report['sources'].items():
            assert sha(evidence/folder/'exact_sources'/name)==digest==sha(repo/name)
            sources.add(name)
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1'
    inputs={f'{name}_training.wav':parent/name/'training.wav' for name in ['A_exterior_low_rev','F2_tailpipe']}
    inputs.update({'data_workspace_AGENTS.md':a.workspace/'AGENTS.md','C_files_sha256.json':old/'C_files_sha256.json',
        'voice_files_sha256.json':old/'voice_files_sha256.json'})
    longest={name:max(len(t['windows']) for t in load(evidence/'observe1'/name/'correspondence.json')['tracks'])
        for name in ['A_exterior_low_rev','F2_tailpipe']}
    assert longest=={'A_exterior_low_rev':2,'F2_tailpipe':3}
    validation=dict(schema='vsl.low-chirp-freeze/1',
        result='local_known_contract_passes_real_persistence_and_mono_source_detection_NOT_qualified',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        python_version=platform.python_version(),observations=observation['observations'],longest_tracks=longest,
        known_moving_and_fixed_tracks=6,known_track_windows=7,mono_noise_conditional_support=1,
        independent_stereo_noise_support=0,source_detector_qualified=False,real_continuous_source_qualified=False,
        audit_windows=18,maximum_wave_error=audit['maximum_wave_error'],
        maximum_explained_error=audit['maximum_explained_error'],known_fixture_error=audit['known_fixture_sample_error'],
        audit1_retained=True,final_audit='audit2',plot_viewed=True,
        supplemental_imports='line_motion __init__/moments unchanged from HEAD, saved with original directly captured dependencies',
        holdout_read=False,shared_phase_fit=False,model_exported=False,new_WAV=False,
        C_H_unchanged=569,voices_unchanged=67,C_tests_repeated=False,runtime_changed=False,
        next='Known nonlinear FM, AM and same-noise stereo distinguish local-model mismatch from persistence/support failures before complex-envelope/finite-coherence observations; retain original shared-phase gates and F2V2 pending listening.')
    info=freeze(root,repo,sources,evidence,inputs,validation)
    save(repo/'research/low_chirp_v1_summary.json',dict(validation,freeze='baselines/low_chirp_v1',**info))
    append_index(repo/'handoff/阶段索引.csv',['low_chirp_v1','baselines/low_chirp_v1/manifest.json',
        str(info['file_count']),info['manifest_sha256'],
        'Known moving3+fixed3 native tracks;18real windows/all candidates/links independently rebuilt;mono-noise counterexample;plot viewed',
        'No real continuous-source qualification;mono1conditional support;no newWAV/profile/C/runtime;569C-H/67voices unchanged',
        'research/低频局部声线与持续性V1.md | research/low_chirp_v1_summary.json',
        'baselines/low_chirp_v1/validation.json | baselines/low_chirp_v1/evidence/audit2/report.json'])
    print(dict(result='frozen',**info))
else:
    manifest=verify(root);summary=load(repo/'research/low_chirp_v1_summary.json')
    assert summary['manifest_sha256']==sha(root/'manifest.json')
    assert load(root/'inputs/C_files_sha256.json')==c and load(root/'inputs/voice_files_sha256.json')==voices
    assert sha(root/'source/tools/package_low_chirp_v1.py')==sha(Path(__file__))
    print(dict(result='verified',files=manifest['file_count'],C_H_unchanged=569,voices_unchanged=67))
