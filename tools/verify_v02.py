"""Audit actual deliverables, untouched sources, page links and baseline hashes."""
from pathlib import Path
from html.parser import HTMLParser
import json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import numpy as np
import soundfile as sf
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href') and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().exists(),value
Links().feed((ROOT/'research/V02试听.html').read_text(encoding='utf-8'))
raw={'references/raw/A_7aZm1Wkp6QM.webm':'fe4a2eb5acaf4776015e1bf25e766bb978fb7e5feaa23faec9f65c91d3329c97',
 'references/raw/B_local_Tecnica_binaural.mp3':'f55989a8a4e33d74121796b7f6916a1bc8ded19390ff5569b411e600549853df'}
for name,digest in raw.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
assert not (Path.home() / 'Desktop' / '2023 Lamborghini Huracan Tecnica - POV Canyon Blast (Binaural Audio).mp3').exists()
for name in ['A_idle_context_v02','A_road_context_v02','A_start_context_v02']:
    path=ROOT/f'references/clean/{name}.wav';p=json.loads(Path(str(path)+'.provenance.json').read_text())
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and x.shape[1]==2 and abs(x).max()<.999
    assert p['source_id']=='A' and not p['normalization'] and not p['denoise']
smoke=json.loads((ROOT/'renders/ui_smoke.json').read_text())
for key in ['waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert smoke[key],key
assert smoke['dsp']=='0.2.0' and smoke['profile_count']==5
assert .95<smoke['device_seconds']/smoke['wall_seconds']<1.02,'device time lags wall clock'
assert smoke['queue_empty_observations']==0,'audio queue starved during smoke test'
assert smoke['render_ms_mean']<smoke['block_frames']/48,'mean render cost exceeds buffer duration'
verify=json.loads((ROOT/'renders/v0.2.0/verification.json').read_text())
for name,case in verify['cases'].items():assert hashlib.sha256((ROOT/f'renders/v0.2.0/{name}.wav').read_bytes()).hexdigest()==case['sha256'],name
assert verify['cases']['v10_drive_714']['channels']==12 and verify['cases']['v10_drive_714']['speaker_mask']=='0x2d63f'
scene=json.loads((ROOT/'renders/v0.2.0/scene.json').read_text())
assert len(scene['objects'])==10 and len(scene['channels'])==12
for item in scene['objects']:assert hashlib.sha256((ROOT/'renders/v0.2.0'/item['file']).read_bytes()).hexdigest()==item['sha256']
for version in ['v0.1.0','v0.2.0']:
    folder=ROOT/'baselines'/version;manifest=json.loads((folder/'manifest.json').read_text())
    for item in manifest['files']:assert hashlib.sha256((folder/item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
report=dict(result='pass',raw_sources_unchanged=True,desktop_source_relocated=True,new_stereo_excerpts=3,
    all_page_targets_exist=True,smoke=smoke,render_count=len(verify['cases']),object_stems=10,
    prior_and_current_baseline_hashes_valid=True,
    remaining=['Exact video state timing and RPM/load calibration','Subjective naturalness review','Physical 7.1.4 audition'])
(ROOT/'renders/v0.2.0/workspace_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
