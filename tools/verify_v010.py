"""Audit lifecycle review, source evidence and frozen history; goal stays active."""
import csv
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from runtime_review import ROOT, sha, rms
from reference_segments import CATALOG, catalog, checked_source, read_segment
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/v0.10.0'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def progress():
    previous=read(ROOT/'research/goal_progress_v09.json')
    full=previous['full_objective_audit']
    full[1].update(status='Incomplete: continuous causal startup fixes an RPM discontinuity and drives distinct layer envelopes. Dominant high-RPM timbre, measured state spectra and subjective realism remain unaccepted.',evidence='research/V010试听.html; research/V010连续启动.md')
    full[2].update(status='Partial: canonical segment bounds, 29 exact-PTS startup frames and raw stereo observations. Cluster layout and audio intervals do not establish aligned ignition/catch times or RPM telemetry.',evidence='references/segments_v1.json; references/analysis/lifecycle_v1/observations.json; research/lifecycle_evidence_v010.json')
    full[3].update(status='Ten independent source stems remain identical between stereo and 7.1.4 export. Physical transfer and actual array listening remain incomplete.',evidence='renders/v0.10.0/drive_714_scene.json')
    full[4].update(status='Partial: lifecycle controller/profile separated, starter speed retained at catch entry, causal flare/settle, safe cancellation and existing sport policy. Startup is an engineering envelope; torque/inertia and moving-engine shutdown remain incomplete.',evidence='src/drive/lifecycle.c; src/profiles/lifecycle.c; tests/test_lifecycle.c')
    result=dict(goal_status='active',review_version='0.10.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Versioned reference segment catalog and hash/allowed-use/stereo-preserving reader',
            'Reproducible startup frame PTS/hash ledger and unmodified stereo time-frequency observations',
            'Independent lifecycle/profile modules, continuous catch RPM and causal six-layer flare',
            'Five shared-gain old/new pairs; ten stereo/7.1.4 source objects identical',
            'Twelve CTests, actual muted UI/preset/device and browser checks; original media and nine baselines preserved'],
        evidence=dict(review='research/V010试听.html',implementation='research/V010连续启动.md',audit='renders/v0.10.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=[
            'Subjective startup audition and dominant high-RPM timbre acceptance',
            'Resolve reference harmonic/order and RPM ambiguity before calibrating RPM/load/state spectral maps',
            'Identify intake/exhaust/body/room transfer with held-out passages and actual spatial listening',
            'Physical torque/inertia, cold/warm/failed starts and moving-engine-off clutch/coasting policy',
            'Keep broad goal active; numeric consistency and UI/device checks are not perceptual realism'])
    (ROOT/'research/goal_progress_v010.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    r=read(OUT/'verification.json');assert r['version']=='0.10.0' and r['seed']==48271
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(ROOT/'build-v010/Release'/name)==digest,name
    assert len(r['cases'])==5
    for name,takes in r['cases'].items():
        gains=[]
        for tag in ['v09','v010']:
            item=takes[tag];audio=OUT/f'{name}_{tag}.wav';x,rate=sf.read(audio,always_2d=True)
            assert sha(audio)==item['sha256'] and rate==48000 and np.isfinite(x).all()
            a=item['audition'];path=OUT/a['file'];y,sr=sf.read(path,always_2d=True)
            assert sha(path)==a['sha256'] and sr==rate and y.shape==x.shape
            assert sf.info(path).subtype=='PCM_24' and abs(y).max()<=.850001
            assert np.max(abs(y-x*10**(a['gain_db']/20)))<1.3e-7
            assert abs(rms(y)-rms(x)-a['gain_db'])<.001
            gains.append(a['gain_db'])
            with (OUT/f'{name}_{tag}.csv').open(newline='') as f:
                rows=list(csv.DictReader(f));assert rows and all(None not in row for row in rows)
        assert gains[0]==gains[1]
    tests=ET.parse(OUT/'ctest.xml').getroot();assert tests.attrib['tests']=='12' and tests.attrib['failures']=='0'
    assert any(c.attrib['name']=='continuous_lifecycle' for c in tests.findall('testcase'))
    d=r['device'];assert d==read(OUT/'ui_smoke.json') and d['dsp']=='0.10.0'
    for key in ['device_stream_muted','waveOut_opened_and_queued_audio','running_latch','manual_shift','shutdown_to_off','export_succeeded',
        'fuel_controls','fuel_preset_roundtrip','control_isolation','mechanical_control','mechanical_preset_roundtrip',
        'legacy_preset_retains_mechanical_voice','combustion_control','combustion_preset_roundtrip','legacy_preset_retains_pressure_voice']:
        assert d[key],key
    assert d['queue_empty_observations']==0 and .95<d['device_seconds']/d['wall_seconds']<1.02 and d['render_ms_mean']<512/48
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==10 and browser['reference_metadata_loads']==2
    scene=read(OUT/'drive_714_scene.json');assert scene['dsp_version']=='0.10.0' and len(scene['objects'])==10
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path=OUT/obj['file'];assert sha(path)==obj['sha256'] and path.read_bytes()==(OUT/f'stems/drive_v010_{obj["name"]}.wav').read_bytes()
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):
                    assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V010试听.html').read_text(encoding='utf-8'))
    media={}
    for identity in ['A','B']:
        source=checked_source(identity);media[identity]={key:source[key] for key in ['raw','raw_sha256','master','master_sha256']}
    for name,item in catalog()['segments'].items():
        x,sr,p=read_segment(name,item['allowed_uses'][0]);assert len(x)==round((item['seconds'][1]-item['seconds'][0])*sr) and x.shape[1]==2
        if item['existing_audition']:
            path=ROOT/item['existing_audition'];derivative=read(path.with_name(path.name+'.provenance.json'))
            assert sha(path)==derivative['output_sha256'] and not derivative['normalization'] and not derivative['denoise']
            assert derivative['start']==item['seconds'][0] and derivative['duration']==item['seconds'][1]-item['seconds'][0]
    obs=read(ROOT/'references/analysis/lifecycle_v1/observations.json')
    assert obs['script_sha256']==sha(ROOT/'tools/analyze_lifecycle_reference.py') and obs['audio']['catalog_sha256']==sha(CATALOG)
    video=obs['video'];assert sha(ROOT/video['video'])==video['video_sha256'] and len(video['frames'])==29
    for row in video['frames']:assert sha(ROOT/'references/analysis/lifecycle_v1'/row['file'])==row['sha256']
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js')=='28d6339bb6c308ed7f4d728d2c7f8e5c65f8fb869822b33c4c88c1f66b9ab759'
    preserved={}
    for version,count in [(1,23),(2,64),(3,81),(4,99),(5,112),(6,161),(7,157),(8,182),(9,190)]:
        folder=ROOT/f'baselines/v0.{version}.0';manifest=read(folder/'manifest.json');assert len(manifest['files'])==count
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],(version,item['path'])
        preserved[f'v0.{version}.0']=count
    progress()
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    files=['README.md','AGENTS.md','build.ps1','Launch.cmd','references/segments_v1.json','research/V010试听.html',
        'research/V010连续启动.md','research/lifecycle_evidence_v010.json','research/goal_progress_v010.json']
    files+=['tools/'+n for n in ['reference_segments.py','analyze_lifecycle_reference.py','render_v010_review.py','make_v010_review.py',
        'verify_v010.py','freeze_v010.py','runtime_review.py','review_pairs.py','comparison_page.py','verify_review_player.cjs','capture_preview.py']]
    audit=dict(result='pass',version='0.10.0',ctest_count=12,shared_gain_pairs=5,stereo_714_identical_sources=10,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in files},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        reference_artifacts={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted((ROOT/'references/analysis/lifecycle_v1').iterdir()) if p.is_file()},
        preserved_baselines=preserved,approved_media=media,
        full_goal='active: startup continuity verified; main timbre, measured state spectra, physical dynamics and actual spatial listening incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.10.0',ctests=12,pairs=5,frames=29,preserved=preserved,goal='active'),indent=2))


if __name__=='__main__':main()
