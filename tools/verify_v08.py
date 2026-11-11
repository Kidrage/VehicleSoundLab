"""Audit V08 output, old history and the still-open full driving/sound objective."""
from pathlib import Path
from html.parser import HTMLParser
import json
import struct
import xml.etree.ElementTree as ET
from runtime_review import ROOT,sha,rms
from verify_v06 import audit_preservation
from render_v07_review import traces
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.8.0'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def progress():
    previous=read(ROOT/'research/goal_progress_v07.json');full=previous['full_objective_audit']
    full[1].update(status='Incomplete: causal rotating/fired structural modes replace fixed carriers; mechanical source is subtle. Dominant exhaust/DNA RPM-load maps, cycle realism and subjective naturalness remain unproven.',evidence='research/V08试听.html; renders/v0.8.0/mechanical_measurements.json')
    full[2].update(status='Partial: four approved mixed-recording texture observations added, with preserved stereo power. They cannot identify block modes, valve timing or ECU/RPM/load telemetry. No new B video evidence.',evidence='references/analysis/mechanical_texture_v1; references/analysis/overrun_v1')
    full[3].update(status='Current source/routing/file implementation verified; ten sources identical across stereo and 7.1.4, mono mechanical object retained. General transfer calibration and physical array listening remain incomplete.',evidence='renders/v0.8.0/drive_714_scene.json; tests/test_spatial.c')
    full[4].update(status='Partial: sport policy, shift/rev match, fuel supply, crank-driven structural impacts, starter rotation and finite ringdown implemented. Physical torque/inertia, measured pipes/cams, intake and lifecycle calibration remain incomplete.',evidence='src/core/mechanical_modal.c; src/core/modal.c; src/drive; tests/test_mechanical.c')
    result=dict(goal_status='active',review_version='0.8.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Damped structural modes and fractional crank-scheduled rotating/fired impacts, independent variation streams and ringdown',
            'Smoothed exact legacy bypass; old presets without selector preserve old mechanical model',
            'Four approved mixed-recording observations with explicit non-identifiability limits',
            'Eight mixed and five isolated shared-gain pairs; unchanged nonmechanical sources, vehicle histories, Pure OSC and all old template bypasses',
            'Ten CTests, DNA interchange, native controls/presets/muted device timing, 26 browser metadata/playback switches and 7.1.4 source equality',
            'Seven frozen baselines and original/float media preserved'],
        evidence=dict(review='research/V08试听.html',implementation='research/V08受激机械共振.md',audit='renders/v0.8.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=[
            'Subjective assessment; focus dominant exhaust/DNA RPM-load-state spectra and controlled cycle variation with held-out references',
            'Measured intake/exhaust/body/room transfer and independent per-car mode/voicing profiles; current settings remain engineering',
            'Stronger synchronized video/event telemetry and physical torque/inertia, startup/shutdown behaviour',
            'Actual stereo/7.1.4 listening and calibrated array playback; signal checks are not perceptual acceptance',
            'Keep the full goal active; frozen V08 is progress, not completion'])
    (ROOT/'research/goal_progress_v08.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    report=read(OUT/'verification.json');assert report['version']=='0.8.0' and report['seed']==48271
    for name,digest in report['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in report['binaries'].items():assert sha(ROOT/'build-v08/Release'/name)==digest,name
    audition={};trace_rows={}
    def pair(takes):
        gains=[]
        for tag in ['legacy','driven']:
            item=takes[tag];path=OUT/item['file'];x,sr=sf.read(path,always_2d=True);info=sf.info(path)
            assert sha(path)==item['sha256'] and sr==48000 and info.subtype=='PCM_24'
            assert info.channels==item['channels'] and np.isfinite(x).all() and float(abs(x).max())<=.850001
            assert abs(rms(x)-item['raw_rms_dbfs']-item['gain_db'])<.001
            gains.append(item['gain_db']);audition[path.name]=dict(sha256=sha(path),channels=info.channels,gain_db=item['gain_db'])
        assert gains[0]==gains[1]
    assert len(report['cases'])==8 and len(report['isolated'])==5
    for name,takes in report['cases'].items():
        pair({tag:takes[tag]['audition'] for tag in ['legacy','driven']})
        assert (OUT/f'{name}_legacy.wav').read_bytes()==(OUT/f'{name}_v07.wav').read_bytes(),name
        trace_rows[name]=traces(OUT/f'{name}_v07.csv',OUT/f'{name}_driven.csv')
        files=report['legacy_compatibility'][name].get('unchanged_source_stems',[])
        if files:
            assert len(files)==9
            for path in files:assert (OUT/'stems'/path).read_bytes()==(OUT/'stems'/path.replace('_legacy_','_driven_')).read_bytes(),path
    for takes in report['isolated'].values():pair(takes)
    for profile in range(5):
        a,b=[OUT/f'compat_profile{profile}_{tag}.wav' for tag in ['v07','v08']]
        assert a.read_bytes()==b.read_bytes() and sha(a)==report['template_bypass'][str(profile)]
    assert (OUT/'lift_pure_v07.wav').read_bytes()==(OUT/'lift_pure_v08.wav').read_bytes()
    tests=ET.parse(OUT/'ctest.xml').getroot();assert tests.attrib['tests']=='10' and tests.attrib['failures']=='0'
    assert 'driven_mechanical_resonators' in {x.attrib['name'] for x in tests.findall('testcase')}
    dna=read(OUT/'dna_check/dna_pipeline_check.json')
    assert dna['result']=='pass' and dna['dsp_version']=='0.8.0' and dna['renderer_sha256']==report['binaries']['vsl_render.exe']
    device=read(OUT/'ui_smoke.json');assert device==report['device']
    for key in ['fuel_controls','fuel_preset_roundtrip','mechanical_control','mechanical_preset_roundtrip',
        'legacy_preset_retains_mechanical_voice','control_isolation','device_stream_muted','waveOut_opened_and_queued_audio',
        'export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert device[key],key
    assert device['queue_empty_observations']==0 and .95<device['device_seconds']/device['wall_seconds']<1.02
    assert device['render_ms_mean']<512/48
    preset=(OUT/'ui_control_roundtrip.ini').read_text()
    assert all(s in preset for s in ['mechanical_model=0','fuel_cut=0','pumping=0.42','release_time=0.32'])
    legacy=(OUT/'ui_legacy_preset.ini').read_text();assert 'version=0.7.0' in legacy and 'mechanical_model' not in legacy
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==26 and browser['reference_metadata_loads']==1
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['href','src'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V08试听.html').read_text(encoding='utf-8'))
    measurement=read(OUT/'mechanical_measurements.json')
    assert measurement['result']=='pass' and measurement['script_sha256']==sha(ROOT/'tools/analyze_v08_mechanical.py')
    for key in ['inputs','plots']:
        for name,digest in measurement[key].items():assert sha(OUT/name)==digest,name
    observation=read(ROOT/'references/analysis/mechanical_texture_v1/results.json')
    assert observation['script_sha256']==sha(ROOT/'tools/analyze_reference_texture.py') and len(observation['recordings'])==4
    for item in observation['recordings']:assert sha(ROOT/item['master'])==item['master_sha256']
    for name,digest in observation['outputs'].items():assert sha(ROOT/'references/analysis/mechanical_texture_v1'/name)==digest
    scene=read(OUT/'drive_714_scene.json')
    assert scene['dsp_version']=='0.8.0' and len(scene['objects'])==10 and scene['parameters']['mechanical_model']==1
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        file=OUT/obj['file'];info=sf.info(file)
        assert sha(file)==obj['sha256'] and info.subtype=='FLOAT' and info.channels==1 and info.frames==1440000
        assert file.read_bytes()==(OUT/f'stems/drive_driven_{obj["name"]}.wav').read_bytes()
    with (OUT/'drive_714_v08.wav').open('rb') as f:
        assert f.read(4)==b'RIFF';f.read(4);assert f.read(4)==b'WAVE';chunks={}
        while True:
            name,size=struct.unpack('<4sI',f.read(8))
            if name==b'data':break
            chunks[name]=f.read(size)
            if size%2:f.read(1)
    assert struct.unpack('<HHI',chunks[b'fmt '][:8])==(65534,12,48000)
    assert struct.unpack('<I',chunks[b'fmt '][20:24])[0]==0x2d63f
    preserved=audit_preservation()
    for version,count in [('v0.6.0',161),('v0.7.0',157)]:
        folder=ROOT/'baselines'/version;manifest=read(folder/'manifest.json');assert len(manifest['files'])==count
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],item['path']
        preserved['frozen_baseline_files_verified'][version]=count
    upstream=read(ROOT/'references/analysis/overrun_v1/results.json')['upstream']
    assert sha(ROOT/'research/upstream/gen/v10_powertrain.gendsp')==upstream['gen_sha256']
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js')==upstream['drive_controller_sha256']
    # Preceding analysis remains a frozen, independently verifiable result.
    previous=read(ROOT/'renders/v0.7.0/workspace_audit.json')
    for name,digest in previous['deliverables'].items():
        if name.startswith('research/') and name!='research/goal_progress_v07.json':assert sha(ROOT/name)==digest,name
    progress()
    source=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=[ROOT/p for p in ['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V08试听.html',
        'research/V08受激机械共振.md','research/goal_progress_v08.json']]
    deliverables += [ROOT/'tools'/p for p in ['render_v08_review.py','analyze_v08_mechanical.py','analyze_reference_texture.py',
        'make_v08_review.py','verify_v08.py','freeze_v08.py','runtime_review.py','comparison_page.py','render_v07_review.py',
        'verify_v06.py','check_dna_pipeline.py','verify_review_player.cjs','capture_preview.py']]
    audit=dict(result='pass',version='0.8.0',ctest_count=10,audition_files=audition,trace_rows_verified=trace_rows,
        legacy_bypass_cases_bit_identical=8,legacy_template_bypass_bit_identical=5,
        unchanged_nonmechanical_stems=9,unchanged_stem_pairs=7,pure_osc_bit_identical=True,
        measurements=measurement,reference_analysis=observation,device=device,browser=browser,dna_pipeline=dna,
        spatial=dict(objects=10,channels=12,channel_mask='0x2d63f',stereo_bed_stems_identical=10,physical_listening=False),
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(source)},
        deliverables={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(deliverables)},
        upstream=upstream,**preserved,limits=report['limits'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',ctests=10,audition_pairs=13,legacy_bypass_cases=8,device=device,
        frozen=preserved['frozen_baseline_files_verified']),indent=2))


if __name__=='__main__':main()
