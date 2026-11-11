"""Validate V09 evidence without substituting mechanism checks for realism."""
from pathlib import Path
from html.parser import HTMLParser
import json
import struct
import xml.etree.ElementTree as ET
from runtime_review import ROOT,sha,rms
from verify_v06 import audit_preservation
from render_v07_review import traces
from render_v09_review import DEVICE_KEYS
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.9.0'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))


def write_progress():
    full=read(ROOT/'research/goal_progress_v08.json')['full_objective_audit']
    full[1].update(status='Incomplete: bounded bank pressure amplitude/arrival variation affects dominant low/high exhaust OSC coherently; actual stationary repeat error changes. This does not prove naturalness or measured RPM/load spectral/transfer calibration.',evidence='research/V09试听.html; renders/v0.9.0/pressure_measurements.json')
    full[2].update(status='Partial: additional mixed-recording L/R band observations and current V6 HEAD/code evidence. Microphone channels are not engine banks; no COV/ignition timing identification, precise RPM/load or new video telemetry.',evidence='references/analysis/pressure_variation_v1; research/upstream_head_v09.json')
    full[3].update(status='Current independent source/routing/export checks pass, including ten identical source stems across stereo and 7.1.4. Physical source-to-listener transfer calibration and actual array audition remain incomplete.',evidence='renders/v0.9.0/drive_714_scene.json; tests/test_spatial.c')
    full[4].update(status='Partial: existing sport drivetrain, shift/refuel, structural impacts and acoustic pressure interval variation remain separated. Physical torque/inertia, full pressure-to-structure coupling, pipes/intake and start/stop calibration remain incomplete.',evidence='src/core/combustion.c; src/drive; tests/test_combustion.c')
    result=dict(goal_status='active',review_version='0.9.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Bounded per-bank pressure amplitude/arrival coefficients, smooth midpoint window and shared low/high OSC modulation',
            'Independent drivetrain crank, no forced inverse periodic AM at full model depth, conservative phase-warp frequency margin',
            'Exact V08 bypass, zero-depth and strict Pure OSC/imported DNA policies; other four templates unchanged',
            'Approved reference L/R local-level observations and freshly verified pinned V6 HEAD/actual Gen lines',
            'Nine mixed plus three source pairs with common gain, seven unaffected objects and stereo/7.1.4 source equality',
            'Eleven CTests, DNA interchange, actual UI/new and historical presets, muted device timing and 24 browser switches',
            'Eight prior frozen baselines and original/float media preserved'],
        evidence=dict(review='research/V09试听.html',implementation='research/V09逐次燃烧压力.md',audit='renders/v0.9.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=['Subjective check of buzz, grain and sharp high-RPM voice; bounded variation is not acceptance',
            'Calibrate dominant RPM/load/state spectral maps and intake/exhaust/body/room transfer with held-out passages',
            'Improve synchronized video/event evidence, physical torque/inertia, pressure-to-structure consistency and lifecycle behaviour',
            'Actual stereo/7.1.4 listening and measured source-to-listener transfer; recording L/R is not physical bank separation',
            'Keep the broad goal active; frozen V09 is concrete progress, not completed real-car simulation'])
    (ROOT/'research/goal_progress_v09.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    report=read(OUT/'verification.json');assert report['version']=='0.9.0' and report['seed']==48271
    for name,digest in report['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in report['binaries'].items():assert sha(ROOT/'build-v09/Release'/name)==digest,name
    audition={};trace_rows={}
    def pair(takes):
        gains=[]
        for tag in ['bypass','varied']:
            item=takes[tag];path=OUT/item['file'];x,sr=sf.read(path,always_2d=True);info=sf.info(path)
            assert sha(path)==item['sha256'] and sr==48000 and info.subtype=='PCM_24' and info.channels==2
            assert np.isfinite(x).all() and float(abs(x).max())<=.850001
            assert abs(rms(x)-item['raw_rms_dbfs']-item['gain_db'])<.001
            gains.append(item['gain_db']);audition[path.name]=dict(sha256=sha(path),gain_db=item['gain_db'])
        assert gains[0]==gains[1]
    assert len(report['cases'])==9 and len(report['isolated'])==3
    for name,takes in report['cases'].items():
        pair({tag:takes[tag]['audition'] for tag in ['bypass','varied']})
        if name!='stress':
            assert (OUT/f'{name}_bypass.wav').read_bytes()==(OUT/f'{name}_v08.wav').read_bytes()
            trace_rows[name]=traces(OUT/f'{name}_v08.csv',OUT/f'{name}_varied.csv')
        files=report['legacy_compatibility'][name]['unchanged_source_stems'];assert len(files)==7
        for path in files:assert (OUT/'stems'/path).read_bytes()==(OUT/'stems'/path.replace('_bypass_','_varied_')).read_bytes()
    for takes in report['isolated'].values():pair(takes)
    for profile in range(5):
        a,b=[OUT/f'compat_profile{profile}_{tag}.wav' for tag in ['v08','bypass']]
        assert a.read_bytes()==b.read_bytes() and sha(a)==report['template_bypass'][str(profile)]
        if profile:assert a.read_bytes()==(OUT/f'compat_profile{profile}_enabled.wav').read_bytes()
    for a,b in [('lift_pure_v08.wav','lift_pure_v09.wav'),('zero_bypass.wav','zero_varied.wav'),('imported_engine_v08.wav','imported_engine_v09.wav')]:assert (OUT/a).read_bytes()==(OUT/b).read_bytes()
    tests=ET.parse(OUT/'ctest.xml').getroot();assert tests.attrib['tests']=='11' and tests.attrib['failures']=='0'
    assert {x.attrib['name'] for x in tests.findall('testcase')}=={'dsp_invariants','driving_states','state_layer_response',
        'high_order_sources','firing_geometry','independent_clocks','transmission_rev_match','fuel_cut_excitation',
        'driven_mechanical_resonators','pressure_event_variation','spatial_objects'}
    dna=read(OUT/'dna_check/dna_pipeline_check.json')
    assert dna['result']=='pass' and dna['dsp_version']=='0.9.0' and dna['renderer_sha256']==report['binaries']['vsl_render.exe']
    device=read(OUT/'ui_smoke.json');assert device==report['device']
    for key in DEVICE_KEYS+['device_stream_muted','waveOut_opened_and_queued_audio','export_succeeded','running_latch','manual_shift','shutdown_to_off']:assert device[key],key
    assert device['queue_empty_observations']==0 and .95<device['device_seconds']/device['wall_seconds']<1.02 and device['render_ms_mean']<512/48
    preset=(OUT/'ui_control_roundtrip.ini').read_text();assert all(s in preset for s in ['combustion_variation=0','mechanical_model=0','fuel_cut=0','pumping=0.42','release_time=0.32'])
    old=(OUT/'ui_v08_preset.ini').read_text();assert 'combustion_variation' not in old and 'mechanical_model=1' in old and 'version=0.8.0' in old
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==24 and browser['reference_metadata_loads']==2
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['href','src'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V09试听.html').read_text(encoding='utf-8'))
    measurement=read(OUT/'pressure_measurements.json');assert measurement['result']=='pass' and measurement['script_sha256']==sha(ROOT/'tools/analyze_v09_pressure.py')
    for key in ['inputs','plots']:
        for name,digest in measurement[key].items():assert sha(OUT/name)==digest,name
    for item in measurement['steady_bank_sources'].values():
        assert min(item['varied']['adjacent_720_cycle_difference_to_signal_db'])>max(item['bypass']['adjacent_720_cycle_difference_to_signal_db'])+30
        assert abs(item['varied']['bank_mean_power_dbfs']-item['bypass']['bank_mean_power_dbfs'])<.1
    observation=read(ROOT/'references/analysis/pressure_variation_v1/results.json')
    assert observation['script_sha256']==sha(ROOT/'tools/analyze_pressure_references.py') and len(observation['recordings'])==4
    for item in observation['recordings']:assert sha(ROOT/item['master'])==item['master_sha256']
    for name,digest in observation['outputs'].items():assert sha(ROOT/'references/analysis/pressure_variation_v1'/name)==digest
    for name in ['A_tailpipe_road_pull.wav','B_cabin_pull.wav']:
        clip=ROOT/'references/clean'/name;provenance=read(clip.with_name(clip.name+'.provenance.json'))
        assert sha(clip)==provenance['output_sha256'] and provenance['normalization'] is False and provenance['denoise'] is False
        assert sf.info(clip).channels==2 and abs(provenance['fixed_analysis_gain_db']+6.020599913279624)<1e-9
    upstream=observation['upstream'];head=read(ROOT/'research/upstream_head_v09.json')
    assert head['sha']==upstream['revision']=='ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
    assert sha(ROOT/'research/upstream/gen/v10_powertrain.gendsp')==upstream['gen_sha256']
    scene=read(OUT/'drive_714_scene.json');assert scene['dsp_version']=='0.9.0' and len(scene['objects'])==10 and scene['parameters']['combustion_variation']==1
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        file=OUT/obj['file'];info=sf.info(file)
        assert sha(file)==obj['sha256'] and info.subtype=='FLOAT' and info.channels==1 and info.frames==1440000
        assert file.read_bytes()==(OUT/f'stems/drive_varied_{obj["name"]}.wav').read_bytes()
    with (OUT/'drive_714_v09.wav').open('rb') as f:
        assert f.read(4)==b'RIFF';f.read(4);assert f.read(4)==b'WAVE';chunks={}
        while True:
            name,size=struct.unpack('<4sI',f.read(8))
            if name==b'data':break
            chunks[name]=f.read(size)
            if size%2:f.read(1)
    assert struct.unpack('<HHI',chunks[b'fmt '][:8])==(65534,12,48000) and struct.unpack('<I',chunks[b'fmt '][20:24])[0]==0x2d63f
    preserved=audit_preservation()
    for version,count in [('v0.6.0',161),('v0.7.0',157),('v0.8.0',182)]:
        folder=ROOT/'baselines'/version;manifest=read(folder/'manifest.json');assert len(manifest['files'])==count
        for item in manifest['files']:assert sha(folder/item['path'])==item['sha256'],item['path']
        preserved['frozen_baseline_files_verified'][version]=count
    for item in read(ROOT/'baselines/v0.8.0/manifest.json')['files']:
        if item['path'].startswith('research/') and (ROOT/item['path']).exists():assert sha(ROOT/item['path'])==item['sha256'],item['path']
    write_progress()
    source=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=[ROOT/p for p in ['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V09试听.html','research/V09逐次燃烧压力.md','research/goal_progress_v09.json','research/upstream_head_v09.json']]
    deliverables += [ROOT/'tools'/p for p in ['render_v09_review.py','analyze_v09_pressure.py','analyze_pressure_references.py','make_v09_review.py','verify_v09.py','freeze_v09.py',
        'review_pairs.py','runtime_review.py','comparison_page.py','render_v08_review.py','render_v07_review.py','verify_v06.py','check_dna_pipeline.py','verify_review_player.cjs','capture_preview.py']]
    audit=dict(result='pass',version='0.9.0',ctest_count=11,audition_files=audition,trace_rows_verified=trace_rows,
        legacy_bypass_cases_bit_identical=8,legacy_template_bypass_bit_identical=5,other_templates_bit_identical=4,
        strict_osc_and_zero_amount_and_imported_bit_identical=True,unchanged_objects=7,unchanged_object_pairs=9,
        measurements=measurement,reference_analysis=observation,current_upstream_head=head,device=device,browser=browser,dna_pipeline=dna,
        spatial=dict(objects=10,channels=12,channel_mask='0x2d63f',stereo_714_stems_identical=10,physical_listening=False),
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(source)},
        deliverables={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(deliverables)},**preserved,limits=report['limits'])
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',ctests=11,common_gain_pairs=12,legacy_bypass_cases=8,device=device,frozen=preserved['frozen_baseline_files_verified']),indent=2))


if __name__=='__main__':main()
