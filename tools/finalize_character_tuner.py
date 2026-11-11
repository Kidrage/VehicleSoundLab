"""Independently inspect UI exports, preserve frozen engines and seal review."""
import json
import shutil
import struct
import subprocess
from pathlib import Path
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/character_tuner_v1'
SNAP=ROOT/'baselines/character_tuner_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def riff_metadata(path):
    data=path.read_bytes();assert data[:4]==b'RIFF' and data[8:12]==b'WAVE'
    assert struct.unpack_from('<I',data,4)[0]==len(data)-8
    offset=12;metadata=None;frames=None;format=None;sample_bytes=None
    while offset<len(data):
        tag=data[offset:offset+4];size=struct.unpack_from('<I',data,offset+4)[0]
        body=data[offset+8:offset+8+size];assert len(body)==size
        if tag==b'fmt ':format=struct.unpack('<HHIIHH',body)
        elif tag==b'fact':frames=struct.unpack('<I',body)[0]
        elif tag==b'data':sample_bytes=size
        elif tag==b'LIST':
            assert body[:4]==b'INFO' and body[4:8]==b'ICMT';n=struct.unpack_from('<I',body,8)[0]
            metadata=json.loads(body[12:12+n].rstrip(b'\0').decode('utf-8'))
        offset+=8+size+(size%2)
    assert offset==len(data) and format==(3,2,48000,384000,8,32)
    assert frames*8==sample_bytes and metadata
    return metadata


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve final tuner review.')
    manifest=read(OUT/'manifest.json');browser=read(OUT/'browser_qa.json')
    assert browser['result']=='pass' and browser['casesLoaded']==6 and not browser['javascriptErrors']
    for key in ['sourceStartsIdentical','controlsIndependent','keyboardRange','baselinePreservesParametersAndTransport',
        'loopWrapAndExit','loopEndpointFadeAndRawBufferPreservation','settingsRoundtrip','offgridSettingsRetained',
        'baselineAndCandidateExports','invalidSettingsPreserveState','corruptAssetStopsAndDisablesExport']:assert browser[key],key
    checks=browser['webAudioMixChecks'];assert len(checks)==3 and sum(len(x['checks']) for x in checks)==18
    assert max(x['maxError'] for row in checks for x in row['checks'])<2e-7
    assert len(manifest['C_checks'])==8 and max(x['max_error'] for x in manifest['C_checks'].values())<1e-7
    for name,row in manifest['cases'].items():
        arrays=[]
        for tag in ['base','pressure','structure']:
            path=OUT/row['assets'][tag]['path'];assert sha(path)==row['assets'][tag]['sha256']
            x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape==(row['frames'],2);arrays.append(x)
        b,p,s=arrays;corners=[b,b+p,b+s,b+p+s]
        assert max(float(abs(x).max()) for x in corners)<.94
        assert max(float(abs(x*row['audition_gain']).max()) for x in corners)<=.800001
    settings=read(OUT/'ui_settings.json');assert settings==browser['exportSettings']
    assert settings['manifest_sha256']==sha(OUT/'manifest.json')
    saved=manifest['cases'][settings['case']]
    args=[str(ROOT/'baselines/character_v1/bin/character_probe.exe'),'render',
        str(ROOT/'renders/character_v1'/f'{settings["case"]}.vsltake'),str(OUT/'checks/ui_download_directC'),
        str(settings['pressure']),str(settings['structure']),'2']
    done=subprocess.run(args,check=True,capture_output=True,text=True,timeout=90)
    direct,rate=sf.read(OUT/'checks/ui_download_directC.wav',always_2d=True);assert rate==48000
    exported={}
    for name,baseline in [('ui_export.wav',False),('ui_export_baseline.wav',True)]:
        path=OUT/name;meta=riff_metadata(path);expected_meta={**settings,'baseline':baseline};assert meta==expected_meta
        info=sf.info(path);actual,rate=sf.read(path,always_2d=True)
        assert info.subtype=='FLOAT' and actual.shape==(saved['frames'],2) and rate==48000
        if baseline:reference,_=sf.read(OUT/saved['assets']['base']['path'],always_2d=True)
        else:reference=direct
        expected=reference*saved['audition_gain']*settings['volume']
        error=float(abs(actual-expected).max());assert error<1e-7
        assert float(abs(actual).max())<.8 and float(abs(actual[:,0]-actual[:,1]).max())>1e-3
        exported[name]=dict(frames=len(actual),channels=2,subtype=info.subtype,max_error_vs_C=error,
            sha256=sha(path),embedded_settings=meta,loop_did_not_change_duration=True)
    runtime=read(ROOT/'renders/v0.15.0/workspace_audit.json')
    for name,digest in runtime['source_code'].items():assert sha(ROOT/name)==digest,name
    for name in ['Launch.cmd','build.ps1','AGENTS.md']:assert sha(ROOT/name)==runtime['deliverables'][name]
    runtime_bins=read(ROOT/'renders/v0.15.0/verification.json')['binaries']
    for name,digest in runtime_bins.items():assert sha(ROOT/'build-v015/Release'/name)==digest,name
    original=read(ROOT/'renders/character_v1/verification.json')
    for name,digest in original['unchanged_reference_hashes'].items():assert sha(ROOT/name)==digest
    history={}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():continue
        frozen=read(folder/'manifest.json')
        for item in frozen['files']:assert sha(folder/item['path'])==item['sha256'],str(folder/item['path'])
        history[folder.name]=len(frozen['files'])
    assert len(history)==17 and history['character_v1']==28
    assert sha(ROOT/'renders/character_v1/results.json')==manifest['source_results_sha256']
    assert sha(ROOT/'renders/character_v1/verification.json')==manifest['source_verification_sha256']
    source_files=list((ROOT/'research/character_tuner').glob('*'))
    source_files += [ROOT/'tools'/name for name in ['prepare_character_tuner.py','verify_character_tuner.cjs','finalize_character_tuner.py']]
    documents=[ROOT/'research'/name for name in ['燃烧与机械调参V1.html','燃烧与机械调参说明V1.md','goal_progress_character_tuner_v1.json']]
    documents.append(ROOT/'README.md')
    audit=dict(result='pass',tool='character_tuner_v1',recipe='Frozen character_v1 unchanged',runtime='0.15.0 unchanged',
        previous_goal_turn='progress: completed frozen character_v1 per-firing pressure/structure audition',
        this_goal_turn='progress: adjustable phase-aligned audition, settings interchange and validated full float export',
        direct_export_C_command=args,direct_export_C_stdout=done.stdout,exports=exported,
        manifest_sha256=sha(OUT/'manifest.json'),C_checks=manifest['C_checks'],web_audio_checks=checks,
        browser_sha256=sha(OUT/'browser_qa.json'),unchanged_runtime_source_files=len(runtime['source_code']),
        unchanged_runtime_binaries=runtime_bins,history=history,
        native_tests='Previous runtime and character C checks preserved; no new DSP/native app/device changes.',
        source_files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in source_files},
        documents={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in documents},
        files={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        goal='Active: character candidate listening, per-car acoustic/state identification, lifecycle/full driving physics and actual array validation remain incomplete.')
    (OUT/'verification.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    SNAP.mkdir()
    for group in ['source_files','documents']:
        for name in audit[group]:
            dest=SNAP/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    for name in ['manifest.json','verification.json','browser_qa.json','ui_settings.json','tuner_desktop.png','tuner_mobile.png']:
        dest=SNAP/'review'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(OUT/name,dest)
    files=[dict(path=str(p.relative_to(SNAP)).replace('\\','/'),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    seal=dict(tool='character_tuner_v1',recipe='character_v1',runtime='0.15.0',runtime_changes=False,
        data_path='renders/character_tuner_v1',files=files,status='Frozen adjustable audition; full user goal active; no additional subjective acceptance.')
    (SNAP/'manifest.json').write_text(json.dumps(seal,indent=2),encoding='utf-8')
    for item in files:assert sha(SNAP/item['path'])==item['sha256']
    print(json.dumps(dict(result='pass',frozen_files=len(files),runtime_source_files_unchanged=len(runtime['source_code']),
        C_checks=8,web_audio_checks=18,exports={k:v['max_error_vs_C'] for k,v in exported.items()},prior_snapshots=len(history)),indent=2))


if __name__=='__main__':main()
