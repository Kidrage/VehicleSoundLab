"""Verify/freeze the isolated completeness diagnostic and immutable history."""
from runtime_review import ROOT,sha,rms
import json
import shutil
import urllib.request
import urllib.parse
import numpy as np
import soundfile as sf

OUT=ROOT/'references/analysis/osc_quality_v2'
SNAPSHOT=ROOT/'baselines/osc_quality_v2'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if SNAPSHOT.exists():raise SystemExit('Preserve frozen quality2; use a new version.')
    report=read(OUT/'results.json')
    old=read(ROOT/'references/analysis/osc_quality_v1/verification.json')
    expected=dict(old['old_snapshot_manifests'])
    expected['osc_quality_v1']=sha(ROOT/'baselines/osc_quality_v1/manifest.json')
    checked={};total=0
    for manifest in sorted((ROOT/'baselines').glob('*/manifest.json')):
        assert sha(manifest)==expected[manifest.parent.name],manifest
        items=read(manifest)['files']
        for item in items:assert sha(manifest.parent/item['path'])==item['sha256'],item['path']
        checked[manifest.parent.name]=sha(manifest);total+=len(items)
    assert len(checked)==41 and total==5777
    native=[v for v in read(ROOT/'baselines/v0.20.0/manifest.json')['files']
            if v['path'].replace('\\','/').startswith(('src/','tests/'))]
    for item in native:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    assert len(native)==170
    prior=read(ROOT/'references/analysis/reference_osc_v2/verification.json')
    for path,identity in prior['source_hashes'].items():assert sha(ROOT/path)==identity,path
    for path,identity in old['protected_originals'].items():assert sha(ROOT/path)==identity,path
    assert sha(ROOT/report['input'])==report['input_sha256']
    assert sha(ROOT/'build-osc-density-v1/Release/dense_osc_probe.exe')==report['probe_sha256']
    reference,sr=sf.read(ROOT/report['input'])
    audition={}
    for name,item in report['variants'].items():
        path=OUT/f'{name}_audition.wav'
        assert sha(path)==item['audition_sha256']
        assert sha(OUT/f'{name}.model')==item['model_sha256']
        x,rate=sf.read(path);info=sf.info(path)
        assert rate==sr==48000 and len(x)==len(reference)==288000 and info.subtype=='PCM_24'
        assert np.isfinite(x).all() and abs(x).max()<.95 and item['C_python_error']<1e-7
        audition[name]=dict(sha256=sha(path),rms_full_dbfs=rms(x),exterior_rms_dbfs=rms(x[124800:278400]))
        if name=='complete':assert np.array_equal(x,reference)
    assert report['controls']['known_AM_chirp']['max_error']<1e-7
    assert report['controls']['truncated']==report['controls']['invalid_bin']=='rejected'
    browser=read(OUT/'browser_qa.json')
    assert browser['loads']==5 and not browser['errors']
    assert all(browser[k] for k in ['muted','http_and_file','position_and_playback_preserved',
                                   'exterior_jump','active_button_stable','narrow_viewport'])
    http={}
    for name in ['OSC完整度对照V2.html','OSC完整度对照V2.md']:
        with urllib.request.urlopen('http://127.0.0.1:8789/research/'+urllib.parse.quote(name),timeout=10) as response:
            assert response.status==200;http[name]=response.status
    sources=[*sorted((ROOT/'experiments/osc_density_v1').glob('*')),
             *sorted((ROOT/'tools/osc_quality_v2').glob('*.py'))]
    evidence={str(p.relative_to(ROOT)):sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='verification.json'}
    verification=dict(result='pass',previous_snapshot_manifests=checked,previous_snapshot_files=total,
        unchanged_native_source_tests=len(native),previous_preview_unchanged=True,native_DSP020_changed=False,
        complete_pcm24_identical_to_recording=True,audition=audition,browser=browser,http=http,
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sources if p.is_file()},evidence_sha256=evidence,
        subjective_acceptance=False,high_tuning_deferred=True,
        limit='Coefficient trajectory preserves recording information; no sustained engine-source or RPM/load inference.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,ensure_ascii=False),encoding='utf-8')
    files=[p for p in sources if p.is_file()]
    files += [p for p in OUT.iterdir() if p.is_file()]
    files += [ROOT/name for name in ['AGENTS.md','README.md','research/OSC完整度对照V2.html',
        'research/OSC完整度对照V2.md','research/goal_progress_osc_quality_v2.json','research/听评记录.md',
        'research/quality_direction_20261110.json','tools/diagnose_osc_quality_v2.py',
        'tools/verify_osc_quality_v2.cjs','tools/audit_osc_quality_v2.py','tools/runtime_review.py',
        'tools/reference_segments.py','tools/seekable_review_player_v1.js','tools/osc_quality_v1/metrics.py',
        'build-osc-density-v1/Release/dense_osc_probe.exe']]
    # Keep the two inputs used directly by this listening page. Earlier full
    # diagnostic snapshots remain separately available in baselines/osc_quality_v1.
    files += [ROOT/'references/analysis/osc_quality_v1'/name for name in ['band_only_audition.wav','legacy64_audition.wav']]
    assert len(files)==len(set(files))
    SNAPSHOT.mkdir();entries=[]
    for source in sorted(files):
        rel=source.relative_to(ROOT);dest=SNAPSHOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest);identity=sha(source);assert sha(dest)==identity
        entries.append(dict(path=rel.as_posix(),sha256=identity))
    manifest=dict(version='osc_quality_v2',status='Capacity diagnostic; listening pending.',
        previous_candidate='quality1 rejected by user: low-quality texture basically unchanged',
        native_application='0.20.0 unchanged',previous_snapshot_manifests=checked,
        previous_review='Earlier V1 page/report are preserved separately in baselines/osc_quality_v1',files=entries)
    (SNAPSHOT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(result='pass',previous_snapshots=len(checked),previous_files=total,
        native_source_tests_unchanged=len(native),new_snapshot_files=len(entries),complete_pcm24_exact=True)))


if __name__=='__main__':main()
