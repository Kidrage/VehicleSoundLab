"""Freeze peak failures, known interference and audited local fits without DNA promotion."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--stage',choices=('publish','freeze','verify'),required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1];base=args.workspace/'references/analysis'
root=base/'F2_local_chirps_v1';peaks=base/'F2_native_peaks_v1';final=root/'final1'
summary=repo/'research/F2_local_chirps_v1_summary.json';frozen=args.workspace/'baselines/F2_local_chirps_v1'

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_current(r):
    for file,digest in r['sources'].items():assert sha(repo/file)==sha(final/'exact_sources'/file)==digest
    for item in r['reports'].values():assert sha(args.workspace/item['path'])==item['sha256']
    for name in ('C_files_sha256.json','voice_files_sha256.json'):
        hashes=load(final/name);assert all(sha(repo/file)==digest for file,digest in hashes.items())
    assert len(load(final/'C_files_sha256.json'))==540
    assert sha(repo/'references/segments_v1.json')==sha(args.workspace/'references/segments_v1.json')==r['catalogue_sha256']
    for item in r['input_media']:assert sha(args.workspace/item['path'])==item['sha256']
    subprocess.run(['git','diff','--exit-code','HEAD','--','src','modules','experiments','voices','CMakeLists.txt'],cwd=repo,capture_output=True,check=True)

if args.stage=='publish':
    final.mkdir(exist_ok=False);r=dict(schema='vsl.F2-local-chirps-final/1',result='running',sources={},reports={})
    try:
        locations={'peak_failure1':peaks/'observe1','peak_failure2':peaks/'observe2',
            'operator_failure':peaks/'interference1','interference':peaks/'interference2',
            'actual':root/'observe1','audit':root/'audit1','review':root/'review1'}
        values={name:load(path/'report.json') for name,path in locations.items()}
        actual=values['actual'];audit=values['audit'];review=values['review']
        assert actual['controls']['passed'] and actual['counts']==dict(observations=90,eligible_frequencies=62,complete_anchor_rows=5)
        assert audit['result']=='native_peak_failures_and_all18_local_chirp_fits_independently_audited'
        assert audit['actual_report_sha256']==review['input_report_sha256']==sha(root/'observe1/report.json')
        assert review['audit_report_sha256']==sha(root/'audit1/report.json')
        assert values['peak_failure1']['result']==values['peak_failure2']['result']=='failed'
        assert not values['peak_failure1']['real_audio_read'] and not values['peak_failure2']['real_audio_read']
        sources={Path(__file__),repo/'AGENTS.md',repo/'research/F2局部联合频率V1.md',
            repo/'research/F2_native_peaks_v1_absence_repair.json',repo/'handoff/研究续接.md',
            repo/'handoff/算法说明.md',repo/'handoff/开发留痕.md',repo/'research/怠速与加速完成度V1.md'}
        versions={}
        for name,value in values.items():
            assert not value['model_exported'] and not value['runtime_changed']
            r['reports'][name]=dict(path=(locations[name]/'report.json').relative_to(args.workspace).as_posix(),
                sha256=sha(locations[name]/'report.json'),result=value['result'])
            for file,digest in value['sources'].items():
                assert sha(locations[name]/'exact_sources'/file)==digest
                if name in ('actual','audit','review'):assert sha(repo/file)==digest
                versions.setdefault(file,{})[name]=digest;sources.add(repo/file)
        for source in sources:
            relative=source.relative_to(repo);target=final/'exact_sources'/relative
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);r['sources'][relative.as_posix()]=sha(source)
        previous=base/'F2_line_motion_v1/final1'
        for name in ('C_files_sha256.json','voice_files_sha256.json'):shutil.copy2(previous/name,final/name)
        shutil.copy2(args.workspace/'AGENTS.md',final/'data_workspace_AGENTS.md')
        assert sha(root/'review1/F2_joint_local_chirps.png')==review['plot_sha256']
        shutil.copy2(root/'review1/F2_joint_local_chirps.png',final/'F2_joint_local_chirps.png')
        source=load(repo/'references/segments_v1.json')['sources']['F2']
        media=[dict(path=source[k],sha256=source[k+'_sha256']) for k in ('raw','master')]
        r.update(result='peak_failures_interference_and18local_chirp_fits_frozen_not_idle_DNA',
            real_audio_read=True,shared_phase_clock_fit=False,local_independent_phase_nuisance_fit=True,
            source_versions=versions,input_media=media,catalogue_sha256=sha(repo/'references/segments_v1.json'),
            counts=actual['counts'],audit_errors=audit['errors'],observation_cell_identity_switches=audit['observation_cell_identity_switches'],
            known_extended_before_max_Hz=max(x['max_frequency_error_Hz'] for x in values['peak_failure2']['controls']['extended_chirp_rows']),
            known_extended_after_max_Hz=max(x['max_frequency_error_Hz'] for x in actual['controls']['extended_chirp_rows']),
            figure_visually_checked=True,C_H=540,C_hashes_sha256=sha(final/'C_files_sha256.json'),
            voice_hashes_sha256=sha(final/'voice_files_sha256.json'),existing55CTests_rerun=False,
            model_exported=False,runtime_changed=False,moving35='held_unchanged',selected_fundamental=None,RPM_inferred=False,
            phase_extracted_real_model_permitted=False,vehicle_timbre_accepted=False,idle_acceleration_complete=False,goal_complete=False,
            original_A_low_listening='original_question_pending',
            previous_goal_turn='progress_AM_observation_bias_repaired_and90real_F2_frequency_moments_independently_audited_frozen_pushed',
            current_goal_turn='progress_actual_native_peak_failures_neighbor_component_diagnosis_and_joint_local_chirp_control_repair_18real_fits_and_independent_audit',
            next_step='Validate cross-window component identity and amplitude versus local chirp mismatch before a continuous phase coordinate; no blind bound/window/degree sweeps. Originalfailed36/all17/full33/individual14k/originalE remain before phase-extracted real models.',
            limits=audit['limits']+actual['limits'])
        verify_current(r);save(summary,r)
    except Exception as exc:r.update(result='failed',error=repr(exc));raise
    finally:save(final/'report.json',r)
    print(json.dumps(dict(result=r['result'],counts=r['counts'])),flush=True)
elif args.stage=='freeze':
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    r=load(summary);verify_current(r);assert sha(summary)==sha(final/'report.json')
    frozen.mkdir(exist_ok=False);shutil.copytree(root,frozen/'evidence');shutil.copytree(peaks,frozen/'peak_evidence')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(frozen/'source.zip'),commit],cwd=repo,check=True)
    files=[dict(path=x.relative_to(frozen).as_posix(),bytes=x.stat().st_size,sha256=sha(x)) for x in sorted(frozen.rglob('*')) if x.is_file()]
    previous={name:dict(path='baselines/'+name+'/manifest.json',sha256=sha(args.workspace/'baselines'/name/'manifest.json')) for name in ('F2_line_motion_v1','state_media_v1')}
    save(frozen/'manifest.json',dict(schema='vsl.freeze/1',source_commit=commit,files=files,prior_manifests=previous,
        real_audio_read=True,profiles_exported=0,vehicle_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='frozen',files=len(files),bytes=sum(x['bytes'] for x in files),commit=commit,manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
else:
    r=load(summary);verify_current(r);m=load(frozen/'manifest.json')
    assert sha(summary)==sha(final/'report.json')==sha(frozen/'evidence/final1/report.json')
    for item in m['files']:assert sha(frozen/item['path'])==item['sha256'] and (frozen/item['path']).stat().st_size==item['bytes']
    with zipfile.ZipFile(frozen/'source.zip') as z:
        assert z.testzip() is None
        for file,digest in r['sources'].items():assert hashlib.sha256(z.read(file)).hexdigest()==digest
    for item in m['prior_manifests'].values():
        path=args.workspace/item['path'];assert sha(path)==item['sha256']
        for row in load(path)['files']:assert sha(path.parent/row['path'])==row['sha256']
    print(json.dumps(dict(result='all_frozen_files_source_zip_prior_payloads_media_C_voices_verified',files=len(m['files']),manifest_sha256=sha(frozen/'manifest.json'))),flush=True)
