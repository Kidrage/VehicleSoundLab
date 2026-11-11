"""Read-only verification and snapshot of the completed character experiment."""
import csv
import json
import shutil
from pathlib import Path
from runtime_review import ROOT,sha
from review_audit import pair
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/character_v1'
SNAP=ROOT/'baselines/character_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve completed experiment.')
    result=read(OUT/'results.json')
    for name,digest in result['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in result['binaries'].items():assert sha(ROOT/name)==digest,name
    assert len(result['cases'])==6
    comparisons={};gates={}
    for name,row in result['cases'].items():
        raw={tag:OUT/f'{name}_{tag}.wav' for tag in result['variants']}
        comparisons[name]=pair(OUT,row['auditions'],list(result['variants']),raw)
        assert row['identical_complete_driving_trace'] and row['identical_stroke_sequence']
        assert row['source_linear_combination_error']<1e-7
        assert (OUT/f'{name}_base.wav').read_bytes()==(OUT/f'{name}_frozen.wav').read_bytes()
        for tag in result['variants']:
            x,rate=sf.read(raw[tag],always_2d=True);assert rate==48000 and np.isfinite(x).all() and x.shape[1]==2
            assert abs(x).max()<.95
        with (OUT/f'{name}_combined_character.csv').open() as f:states=list(csv.DictReader(f))
        checked=0
        for a,b in zip(states,states[1:]):
            nofuel=float(a['fuel_command'])==float(b['fuel_command'])==0
            stopping=a['lifecycle']==b['lifecycle']=='5'
            if nofuel or stopping:
                assert a['event_count']==b['event_count'];checked+=1
        gates[name]=checked
    assert gates['lift']>100
    scene=read(OUT/result['bed714']['scene']);assert scene['dsp_version']=='character_v1 experiment'
    assert scene['base_runtime_version']=='0.15.0' and len(scene['objects'])==10
    for source in scene['objects']:
        assert sha(OUT/source['file'])==source['sha256']
        other=OUT/('high_combined_source_'+source['name']+'.wav')
        assert (OUT/source['file']).read_bytes()==other.read_bytes()
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==24
    assert browser['position_preserved'] and browser['muted_playback_switch_preserved']
    log=(ROOT/'build-experiment-character/Testing/Temporary/LastTest.log').read_bytes();assert log.count(b'Test Passed.')==1
    (OUT/'ctest.log').write_bytes(log)
    runtime=read(ROOT/'renders/v0.15.0/workspace_audit.json')
    for name,digest in runtime['source_code'].items():assert sha(ROOT/name)==digest,name
    for name in ['Launch.cmd','build.ps1','AGENTS.md']:assert sha(ROOT/name)==runtime['deliverables'][name]
    runtime_bins=read(ROOT/'renders/v0.15.0/verification.json')['binaries']
    for name,digest in runtime_bins.items():assert sha(ROOT/'build-v015/Release'/name)==digest,name
    history={}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():continue
        manifest=read(folder/'manifest.json')
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],str(folder/item['path'])
        history[folder.name]=len(manifest['files'])
    assert len(history)==16
    expected={
        'references/raw/A_7aZm1Wkp6QM.webm':'fe4a2eb5acaf4776015e1bf25e766bb978fb7e5feaa23faec9f65c91d3329c97',
        'references/clean/A_decoded_float.wav':'34885942c450127932a25c72a63fdeae59026f30cfe3678a7aba6b1f5f87b964',
        'references/raw/B_local_Tecnica_binaural.mp3':'f55989a8a4e33d74121796b7f6916a1bc8ded19390ff5569b411e600549853df',
        'references/clean/B_decoded_float.wav':'2752235d33ec17776a3bb0a54c49545503318ab004f6f44095610e236547d51f'}
    for name,digest in expected.items():assert sha(ROOT/name)==digest,name
    code=list((ROOT/'experiments/character_v1').glob('*'))
    code += [ROOT/'tools'/n for n in ['render_character_review.py','verify_character.py','comparison_page.py','review_pairs.py']]
    docs=[ROOT/'research'/n for n in ['听评记录.md','燃烧与机械细节实验V1.md','燃烧与机械细节试听V1.html','goal_progress_character_v1.json']]
    docs.append(ROOT/'README.md')
    audit=dict(result='pass',experiment='character_v1',runtime='0.15.0 unchanged',runtime_source_files=len(runtime['source_code']),
        unchanged_runtime_binaries=runtime_bins,unchanged_reference_hashes=expected,history=history,
        ctests='One new experiment integration suite passed; previous 17 runtime CTests preserved, no native runtime/UI/device change.',
        fixed_take_groups=6,variants=4,float_mixes=24,source_stems=250,common_gain_auditions=comparisons,
        ineligible_adjacent_trace_pairs_checked=gates,browser=browser,
        source_files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in code if p.is_file()},
        documents={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in docs},
        files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
        subjective_status='User accepted V011 direction/continuity, wants stronger timbre and combustion/mechanics first. New experiment not yet subjectively reviewed. Full goal active.')
    (OUT/'verification.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    SNAP.mkdir()
    for group in ['source_files','documents']:
        for name in audit[group]:
            target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for name in ['results.json','verification.json','browser_qa.json','ctest.log','listening_desktop.png','listening_mobile.png']:
        target=SNAP/'review'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(OUT/name,target)
    (SNAP/'bin').mkdir();shutil.copy2(ROOT/'build-experiment-character/Release/character_probe.exe',SNAP/'bin/character_probe.exe')
    files=[dict(path=str(p.relative_to(SNAP)).replace('\\','/'),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(experiment='character_v1',base_runtime='0.15.0',default_runtime_changed=False,
        data_path='renders/character_v1',status='Frozen audition candidate; full goal active, no new sound acceptance inferred.',files=files)
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for item in files:assert sha(SNAP/item['path'])==item['sha256']
    print(json.dumps(dict(result='pass',experiment='character_v1',frozen_files=len(files),unchanged_runtime_source_files=len(runtime['source_code']),
        groups=6,variants=4,browser_loads=24,gate_checks=gates,history=history),indent=2))


if __name__=='__main__':main()
