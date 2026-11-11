"""Audit actual integration/exports; keep vehicle identification unproven."""
import json
import math
from html.parser import HTMLParser
from runtime_review import ROOT,sha
from review_audit import read_json as read,pair,device,frozen_baselines
from drivetrain_audit import read_trace,energy_audit
from reference_segments import checked_source
import soundfile as sf
OUT=ROOT/'renders/v0.13.0'


def progress():
    full=read(ROOT/'research/goal_progress_v012.json')['full_objective_audit']
    full[3].update(status='Ten independent sources remain byte-identical across stereo and 7.1.4 with the new coupled drivetrain. Actual listener transfer and physical array listening remain unverified.',evidence='renders/v0.13.0/drive_714_scene.json')
    full[4].update(status='Partial: engine and vehicle inertias now integrate together through passive bounded clutch friction, with idle/launch control, upshift synchronization, open-clutch downshift blips and per-step energy audits. No RPM follower in RUNNING pedal/neutral/shift driving. Identified per-vehicle parameters, lifecycle coupling, full DCT shafts, tyre slip/ABS and calibrated neutral decay remain incomplete.',
        evidence='research/V013曲轴与离合耦合.md; tests/test_coupling.c; tests/test_drive.c; renders/v0.13.0/verification.json')
    result=dict(goal_status='active',review_version='0.13.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Measured frozen V012 torque/RPM consistency defect and rechecked unchanged V6 HEAD',
            'Modular physical engine/vehicle inertias with bounded implicit clutch friction and unilateral rest constraints',
            'Explicit idle/launch/torque-governor controls; passive upshift sync; downshift throttle isolated by open clutch',
            'Separate physical clutch heat, transmission loss and numerical damping; every RUNNING control step accumulated',
            'Fifteen CTests including 12000 energy/passivity controls and integrated no-RPM-overwrite checks',
            'Four common-gain driving pairs, four byte-identical bench outputs, stereo/7.1.4 source identity, real muted native UI/device/browser checks'],
        subjective_review='V011 timbre listening remains pending. V013 is a physical driving review, not accepted car sound or measured vehicle performance.',
        evidence=dict(review='research/V013试听.html',implementation='research/V013曲轴与离合耦合.md',audit='renders/v0.13.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=['Identify reference neutral decay/loss-to-inertia ratio; current free-rev fall may be slow',
            'Reference RPM/load/state spectra and acoustic transfer; automatic harmonic candidates remain ambiguous',
            'Identified per-car dynamics, lifecycle coupling, full multi-shaft DCT, tyre slip/ABS and thermal clutch response',
            'Intake/exhaust transfer, weak full-cycle high components, pressure/body coupling and subjective V011/V013 listening',
            'Calibrated stereo and actual 7.1.4 listening'])
    (ROOT/'research/goal_progress_v013.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    r=read(OUT/'verification.json');assert r['version']=='0.13.0' and r['seed']==48271
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(ROOT/'build-v013/Release'/name)==digest,name
    auditions={};energies={};assert len(r['cases'])==4
    for name,takes in r['cases'].items():
        auditions.update(pair(OUT,{tag:takes[tag]['audition'] for tag in ['v012','v013']},['v012','v013'],raw={tag:OUT/f'{name}_{tag}.wav' for tag in ['v012','v013']}))
        rows=read_trace(OUT/f'{name}_v013.csv');energies[name]=energy_audit(rows)
        assert energies[name]==takes['v013']['energy'] and int(rows[-1]['aborted_shifts'])==0
        if name=='drive':
            lift=[x for x in rows if 14<=float(x['running_seconds'])<17]
            assert len(set(x['gear'] for x in lift))==1 and len(set(x['shifts'] for x in lift))==1
            assert float(rows[-1]['speed_kph'])==0
            sync=[x for x in rows if x['shift_stage']=='MATCH' and x['shift_direction']=='1' and float(x['clutch_torque_nm'])>0]
            assert len(sync)>10 and all(float(x['engine_throttle'])==0 for x in sync)
        if name=='neutral':assert all(float(x['speed_kph'])==0 for x in rows)
        for row in rows:
            if float(row['blip'])>0:assert float(row['wheel_force_n'])==0 and row['shift_stage']=='MATCH'
    for name,digest in r['bench_unchanged'].items():
        old=OUT/f'bench_{name}_v012.wav';new=OUT/f'bench_{name}_v013.wav'
        assert old.read_bytes()==new.read_bytes() and sha(new)==digest
    assert len(r['bench_unchanged'])==4
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==15
    assert b'passive_two_inertia_coupling' in (OUT/'ctest.log').read_bytes()
    device(r['device'],'0.13.0');assert r['device']['two_inertia_coupling_active']
    assert r['device']==read(OUT/'ui_smoke.json')
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==8
    scene=read(OUT/'drive_714_scene.json');assert scene['dsp_version']=='0.13.0' and len(scene['objects'])==10
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path=OUT/obj['file'];assert sha(path)==obj['sha256'] and sf.info(path).subtype=='FLOAT'
        assert path.read_bytes()==(OUT/f'stems/drive_v013_{obj["name"]}.wav').read_bytes()
    for folder in ['core','spatial']:
        for path in (ROOT/'src'/folder).iterdir():
            if path.is_file() and path!=ROOT/'src/core/types.h':assert sha(path)==sha(ROOT/'baselines/v0.12.0'/path.relative_to(ROOT)),path
    observation=read(ROOT/'research/drive_coupling_audit_v013.json')
    assert sha(ROOT/observation['source'])==observation['source_sha256'] and observation['largest_examples'][0]['power_excess_w']>13000
    original_rows=read_trace(ROOT/observation['source'])
    for point in observation['largest_examples']:
        row=next(x for x in original_rows if float(x['seconds'])==point['seconds'])
        supplied=float(row['shaft_torque_nm'])*float(row['force_sample_rpm'])*2*math.pi/60
        demand=float(row['wheel_force_n'])*float(row['force_sample_speed_mps'])/.9
        assert abs(supplied-point['engine_shaft_w'])<1e-6 and abs(demand-point['wheel_equivalent_shaft_w'])<1e-6
        assert abs(demand-supplied-point['power_excess_w'])<1e-6
    upstream=read(ROOT/'research/upstream_head_v013.json')
    assert upstream['sha']=='ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js')==upstream['snapshot_sha256']
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V013试听.html').read_text(encoding='utf-8'))
    history=frozen_baselines({f'v0.{v}.0':count for v,count in [(1,23),(2,64),(3,81),(4,99),(5,112),(6,161),(7,157),(8,182),(9,190),(10,205),(11,189),(12,156)]})
    media={identity:checked_source(identity) for identity in ['A','B']};progress()
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V013试听.html','research/V013曲轴与离合耦合.md',
        'research/goal_progress_v013.json','research/upstream_head_v013.json','research/drive_coupling_audit_v013.json','research/vehicle_specs_v012.json','references/segments_v1.json']
    deliverables+=['tools/'+name for name in ['render_v013_review.py','make_v013_review.py','verify_v013.py','freeze_v013.py','freeze_review.py',
        'drivetrain_audit.py','runtime_review.py','review_pairs.py','review_audit.py','comparison_page.py','verify_review_player.cjs','reference_segments.py']]
    audit=dict(result='pass',version='0.13.0',ctest_count=15,shared_gain_pairs=4,unchanged_bench_cases=4,
        stereo_714_identical_sources=10,approved_media=media,preserved_baselines=history,audition_files=auditions,energy=energies,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},deliverables={name:sha(ROOT/name) for name in deliverables},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; discrete RUNNING mechanics verified, timbre/reference identification/calibrated full dynamics/spatial listening incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.13.0',ctests=15,pairs=4,bench_unchanged=4,source_equality=10,history=history,goal='active'),indent=2))


if __name__=='__main__':main()
