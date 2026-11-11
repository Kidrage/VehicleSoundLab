"""Freeze the LF-only addition; verify older accepted code/media stays exact."""
from runtime_review import ROOT,sha
import json
import shutil
import tempfile
from pathlib import Path

OUT=ROOT/'references/analysis/low_rumble_v2'
NATIVE=ROOT/'references/analysis/sustain_monitor_v4'
SNAPSHOT=ROOT/'baselines/low_rumble_v2'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def hashes(items,base=ROOT):
    for path,identity in items.items():assert sha(base/path)==identity,path


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve low_rumble_v2; use a new version.')
    previous=ROOT/'baselines/sound_dna_v1'
    expected=read(previous/'references/analysis/sound_dna_v1/audit.json')['old_snapshot_manifests']
    expected['sound_dna_v1']=sha(previous/'manifest.json');snapshots={};total=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        items=read(manifest)['files'];hashes({v['path']:v['sha256'] for v in items},manifest.parent)
        snapshots[manifest.parent.name]=sha(manifest);total+=len(items)
    assert set(snapshots)==set(expected) and len(snapshots)==47 and total==6171
    driving=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files'] if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    hashes({v['path']:v['sha256'] for v in driving});assert len(driving)==170
    unchanged_dna=[v for v in read(previous/'manifest.json')['files'] if v['path'].startswith(('modules/sound_dna/','voices/dna_bank_v1/','experiments/sustain_monitor_v3/','build-sustain-monitor-v3/'))]
    hashes({v['path']:v['sha256'] for v in unchanged_dna})
    for context,build in [('detail_osc_v1','build-detail-osc-v1'),('sustain_monitor_v1','build-sustain-monitor-v1'),('sustain_monitor_v2','build-sustain-monitor-v2')]:
        proof=read(ROOT/'references/analysis'/context/'verification.json')
        hashes(proof['source_hashes']);hashes(proof['binaries'],ROOT/build/'Release')
    offline=read(OUT/'verification.json');native=read(NATIVE/'verification.json');browser=read(OUT/'browser_qa.json')
    assert offline['result']==native['result']==browser['result']=='pass'
    for proof in [offline,native]:
        hashes(proof['source_hashes']);hashes(proof['binaries'],ROOT/'build-sustain-monitor-v4/Release')
    hashes(native['evidence'])
    assert browser['loads']==28 and not browser['errors'] and browser['muted']
    assert offline['zero_rumble_exact_previous_monitor'] and offline['DNA_raw_exact_all_profiles']
    assert native['native_matches_offline_default_exactly'] and native['bank_checks']['voice_count']==4
    assert all(native['native'][key]['queue_empty']==0 for key in ['baseline','live','stopped','closed'])
    assert native['native']['baseline']['raw_float_hash']=='89079981f900fd12'
    survey=read(OUT/'survey.json');catalog=read(ROOT/'references/segments_v1.json')
    assert survey['catalog_sha256']==sha(ROOT/'references/segments_v1.json')
    assert set(survey['sources'])=={'A','B','D','E'} and set(survey['segments'])==set(catalog['segments'])
    seconds=0
    for source in survey['sources'].values():
        hashes({source['raw']:source['raw_sha256'],source['master']:source['master_sha256']})
        assert source['scanned_seconds']==source['duration_seconds'];seconds+=source['duration_seconds']
    for item in survey['segments'].values():assert sha(ROOT/item['lf_reference'])==item['lf_reference_sha256']
    bank=read(ROOT/'voices/low_rumble_v2/index.json');assert len(bank['profiles'])==4
    for item in bank['profiles']:
        name=item['name'];proof=offline['profiles'][name]
        assert sha(ROOT/'voices/low_rumble_v2'/item['file'])==item['model_sha256']==proof['model_sha256']
        assert sha(OUT/'renders'/f'{name}_low_raw.wav')==proof['low_sha256']
        assert sha(OUT/'renders'/f'{name}_DNA_raw.wav')==proof['unchanged_DNA_sha256']
        assert sha(OUT/'renders'/f'{name}_solo_audition.wav')==proof['solo_sha256']
        for tag,v in proof['variants'].items():
            assert sha(OUT/'renders'/f'{name}_mix{tag}_float.wav')==v['sha256']
            assert sha(OUT/'renders'/f'{name}_mix{tag}_audition.wav')==v['audition_sha256']
    audit=dict(result='pass',old_snapshot_manifests=snapshots,old_snapshot_files=total,
               driving_source_tests_unchanged=len(driving),accepted_DNA_files_unchanged=len(unchanged_dna),
               source_seconds_scanned=seconds,approved_sources=4,catalogued_contexts=len(survey['segments']),
               zero_low_exact_accepted_monitor=True,DNA_raw_exact_all_low_profiles=True,
               muted_device_queue_empty=0,subjective_low_acceptance=False,goal_complete=False,
               limits='Numeric full-source LF survey and a recording-informed spectral PAD. No full subjective listening, physical source separation or measured RPM/load/room claim.')
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    folders=['modules/low_rumble','modules/sound_dna','experiments/sustain_monitor_v4','tools/low_rumble_v2',
             'voices/low_rumble_v2','references/analysis/low_rumble_v2','references/analysis/sustain_monitor_v4']
    files=[p for folder in folders for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    files += [ROOT/path for path in ['AGENTS.md','README.md','Launch-low-rumble-v2.cmd','research/低频轰鸣V2.md','research/低频轰鸣V2.html',
        'research/听评记录.md','research/goal_progress_low_rumble_v2.json','tools/analyze_low_rumble_v2.py','tools/fit_low_rumble_v2.py',
        'tools/verify_low_rumble_v2.py','tools/verify_sustain_monitor_v4.py','tools/make_low_rumble_v2_review.py',
        'tools/verify_low_rumble_v2.cjs','tools/audit_low_rumble_v2.py','tools/runtime_review.py','tools/reference_segments.py','tools/seekable_review_player_v1.js',
        'voices/dna_bank_v1/V10 Exterior.model','references/approval_manifest.json','references/segments_v1.json',
        'baselines/v0.20.0/src/io/wav.h','baselines/v0.20.0/bin/vsl_core.lib']]
    files += [ROOT/'build-sustain-monitor-v4/Release'/name for name in native['binaries']]
    files += [ROOT/'build-sustain-monitor-v4/low-rumble-core/Release/low_rumble.lib',ROOT/'build-sustain-monitor-v4/sound-dna-core/Release/sound_dna.lib']
    assert len(files)==len(set(files)) and all(p.is_file() for p in files)
    staging=Path(tempfile.mkdtemp(prefix='.low-rumble-v2-',dir=ROOT/'baselines'));entries=[]
    for source in sorted(files):
        rel=source.relative_to(ROOT);dest=staging/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);identity=sha(source);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    manifest=dict(version='low_rumble_v2',scope='Full A/B/D/E LF survey, independent stochastic OSC rumble and separate native monitor.',
                  subjective_low_status='Pending user listening',DNA='Accepted fixed-phase sound_dna_v1 unchanged',
                  driving_DSP='0.20.0 unchanged',old_snapshot_manifests=snapshots,files=entries)
    (staging/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    staging.rename(SNAPSHOT)
    print(json.dumps(dict(result='pass',old_snapshots=len(snapshots),old_files=total,new_snapshot_files=len(entries),scanned_seconds=seconds,accepted_DNA_files_unchanged=len(unchanged_dna)),indent=2))


if __name__=='__main__':main()
