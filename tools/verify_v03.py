"""Audit the actual 0.3.0 files. These checks do not claim perceptual realism."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,struct,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/python_deps'))
import soundfile as sf
OUT=ROOT/'renders/v0.3.0'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
report=json.loads((OUT/'verification.json').read_text())
assert report['version']=='0.3.0'
for rel,sha in report['files'].items():assert digest(OUT/rel)==sha,rel
for source in ['A','B']:
    old=json.loads((ROOT/'references/analysis/state_transitions_v1/results.json').read_text())['sources'][source]
    assert digest(ROOT/old['master'])==old['sha256']
raw={'A_7aZm1Wkp6QM.webm':'fe4a2eb5acaf4776015e1bf25e766bb978fb7e5feaa23faec9f65c91d3329c97',
     'B_local_Tecnica_binaural.mp3':'f55989a8a4e33d74121796b7f6916a1bc8ded19390ff5569b411e600549853df'}
for name,sha in raw.items():assert digest(ROOT/'references/raw'/name)==sha
assert not (Path.home() / 'Desktop' / '2023 Lamborghini Huracan Tecnica - POV Canyon Blast (Binaural Audio).mp3').exists()
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ['src','href'] and not value.startswith(('http:','https:','#')):
                assert (ROOT/'research'/value).resolve().is_file(),value
Links().feed((ROOT/'research/V03试听.html').read_text(encoding='utf-8'))
suite=ET.parse(OUT/'ctest.xml').getroot()
assert suite.attrib['tests']=='4' and suite.attrib['failures']=='0'
assert {n.attrib['name'] for n in suite.findall('testcase')}=={'dsp_invariants','driving_states','state_layer_response','spatial_objects'}
smoke=json.loads((OUT/'ui_smoke.json').read_text())
for key in ['waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off','device_stream_muted']:
    assert smoke[key],key
assert smoke['dsp']=='0.3.0' and smoke['queue_empty_observations']==0
assert .95<smoke['device_seconds']/smoke['wall_seconds']<1.02
assert smoke['render_ms_mean']<smoke['block_frames']/48
assert json.loads((OUT/'dna_pipeline_check.json').read_text())['result']=='pass'
wave=OUT/'v10_drive_714.wav'
with wave.open('rb') as f:
    assert f.read(12)==b'RIFF'+struct.pack('<I',wave.stat().st_size-8)+b'WAVE'
    chunks={}
    while True:
        chunk=f.read(8)
        if not chunk:break
        name,size=struct.unpack('<4sI',chunk)
        if name==b'data':chunks[name]=size;break
        chunks[name]=f.read(size)
        if size%2:f.read(1)
fmt=chunks[b'fmt ']
assert struct.unpack('<HHI',fmt[:8])==(65534,12,48000)
assert struct.unpack('<H',fmt[14:16])[0]==32 and struct.unpack('<I',fmt[20:24])[0]==0x2d63f
assert struct.unpack('<I',fmt[24:28])[0]==3 and chunks[b'data']==30*48000*12*4
assert struct.unpack('<I',chunks[b'fact'][:4])[0]==30*48000
scene=json.loads((OUT/'v10_drive_714_scene.json').read_text())
assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
assert len(scene['objects'])==10
for obj in scene['objects']:
    path=OUT/obj['file'];info=sf.info(path)
    assert info.channels==1 and info.frames==30*48000 and info.subtype=='FLOAT'
    assert digest(path)==obj['sha256']
assert report['sport_auto']['extra_coast_shifts']==0 and report['sport_auto']['safe_downshifts']>=1
assert report['sport_auto']['final_speed_kph']<2
versions=['v0.1.0','v0.2.0']
if (ROOT/'baselines/v0.3.0/manifest.json').exists():versions.append('v0.3.0')
for version in versions:
    folder=ROOT/'baselines'/version
    for item in json.loads((folder/'manifest.json').read_text())['files']:
        assert digest(folder/item['path'])==item['sha256'],(version,item['path'])
audit=dict(result='pass',ctest_tests=4,render_cases=len(report['cases']),
    sport_auto=report['sport_auto'],device=smoke,render_owned_files=len(report['files']),
    verified_baselines=versions,source_hashes_unchanged=True,bed_714_format='float32 extensible, mask 0x2d63f, fact frames verified',
    limits=['No listening acceptance or measured Lamborghini calibration is inferred.',
            'Muted device stream verifies API timing, not audible output or loopback.',
            'Physical 7.1.4 array audition is pending.'])
(OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k not in ['sport_auto']},indent=2))
