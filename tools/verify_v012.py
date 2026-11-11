"""Audit the reduced longitudinal model, without claiming car identification."""
import csv
import json
from html.parser import HTMLParser
from runtime_review import ROOT, sha
from review_audit import read_json as read, pair, device, frozen_baselines
from reference_segments import checked_source
import numpy as np
import soundfile as sf
OUT=ROOT/'renders/v0.12.0'


def progress():
    full=read(ROOT/'research/goal_progress_v011.json')['full_objective_audit']
    full[4].update(status='Partial: SI shaft torque/gearing/forces, rolling/aero/service braking, reflected-inertia proxy and original-gear disconnect are integrated in native driving. Full clutch/two-inertia dynamics, measured vehicle profiles and reference state calibration remain incomplete.',
        evidence='research/V012纵向动力链.md; tests/test_longitudinal.c; renders/v0.12.0/verification.json')
    result=dict(goal_status='active',review_version='0.12.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Official Performante peak torque/power anchors, explicit engineering vehicle proxy shared by five voices',
            'Modular SI shaft torque, gearing, road forces, backdrive loss, service braking and reduced reflected inertia',
            'Original driven gear during disconnect; blip cannot deliver wheel thrust; ignition-off vehicle can brake',
            'Four actual old/new driving pairs at common gain, four byte-identical bench controls, ten stereo/7.1.4 identical sources',
            'Fourteen CTests, native muted audio/UI/preset test confirms active longitudinal model; actual browser review tested'],
        subjective_review='Pending V011 timbre feedback; no subjective acceptance inferred. V012 changes driving response, not the bench source voice.',
        evidence=dict(review='research/V012试听.html',implementation='research/V012纵向动力链.md',audit='renders/v0.12.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=['Reference RPM/load/state spectra and measured acoustic transfer; automatic harmonic spacing remains ambiguous',
            'Complete engine/wheel/clutch inertias and per-vehicle physical calibration; current launch/free-rev RPM follows engineering targets',
            'Intake/exhaust pipe transfer, weak full-cycle high components and pressure-to-body coupling',
            'User listening on V011 source continuity and V012 driving; calibrated stereo/physical 7.1.4 playback'])
    (ROOT/'research/goal_progress_v012.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    r=read(OUT/'verification.json');assert r['version']=='0.12.0' and r['seed']==48271
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(ROOT/'build-v012/Release'/name)==digest,name
    auditions={};assert len(r['cases'])==4
    for name,takes in r['cases'].items():
        auditions.update(pair(OUT,{tag:takes[tag]['audition'] for tag in ['v011','v012']},['v011','v012'],
            raw={tag:OUT/f'{name}_{tag}.wav' for tag in ['v011','v012']}))
        rows=list(csv.DictReader((OUT/f'{name}_v012.csv').open()))
        assert int(rows[-1]['aborted_shifts'])==0
        for row in rows:
            for key in ['force_sample_speed_mps','force_sample_rpm','shaft_torque_nm','wheel_force_n','effective_mass_kg','acceleration_mps2']:
                assert np.isfinite(float(row[key]))
            assert float(row['effective_mass_kg'])>=1670 and int(row['force_gear']) in range(8)
            assert float(row['engine_brake_n'])>=0 and float(row['service_brake_n'])>=0
            assert float(row['service_brake_n'])-float(row['wheel_force_n'])<=1.10*1600*9.80665+.001
            if float(row['force_sample_clutch'])==0 or int(row['force_gear'])==0:assert float(row['wheel_force_n'])==0
        if name=='drive':
            lift=[x for x in rows if 14<=float(x['running_seconds'])<17]
            assert len(set(x['gear'] for x in lift))==1 and len(set(x['shifts'] for x in lift))==1
            assert float(rows[-1]['speed_kph'])==0
        if name=='neutral':assert all(float(row['speed_kph'])==0 for row in rows)
    for name,digest in r['bench_unchanged'].items():
        old=OUT/f'bench_{name}_v011.wav';new=OUT/f'bench_{name}_v012.wav'
        assert old.read_bytes()==new.read_bytes() and sha(new)==digest
    assert len(r['bench_unchanged'])==4
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==14
    assert b'longitudinal_dynamics' in (OUT/'ctest.log').read_bytes()
    device(r['device'],'0.12.0');assert r['device']['longitudinal_model_active']
    assert r['device']==read(OUT/'ui_smoke.json')
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==8
    scene=read(OUT/'drive_714_scene.json');assert scene['dsp_version']=='0.12.0' and len(scene['objects'])==10
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path=OUT/obj['file'];assert sha(path)==obj['sha256'] and sf.info(path).subtype=='FLOAT'
        assert path.read_bytes()==(OUT/f'stems/drive_v012_{obj["name"]}.wav').read_bytes()
    source=read(ROOT/'research/vehicle_specs_v012.json')
    assert source['http_status']==200 and source['source'].startswith('https://www.lamborghini.com/')
    assert source['applied_anchors']==dict(max_torque_nm=600,torque_peak_rpm=6500,max_power_w=470000,power_peak_rpm=8000)
    # No source DSP modules or spatial algorithms were edited in this turn.
    for folder in ['core','spatial']:
        for path in (ROOT/'src'/folder).iterdir():
            if path.is_file() and path!=ROOT/'src/core/types.h':
                assert sha(path)==sha(ROOT/'baselines/v0.11.0'/path.relative_to(ROOT)),path
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V012试听.html').read_text(encoding='utf-8'))
    history=frozen_baselines({f'v0.{v}.0':count for v,count in [(1,23),(2,64),(3,81),(4,99),(5,112),(6,161),(7,157),(8,182),(9,190),(10,205),(11,189)]})
    media={identity:checked_source(identity) for identity in ['A','B']}
    progress()
    sources=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    deliverables=['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V012试听.html','research/V012纵向动力链.md',
        'research/goal_progress_v012.json','research/vehicle_specs_v012.json','references/segments_v1.json']
    deliverables+=['tools/'+name for name in ['render_v012_review.py','make_v012_review.py','verify_v012.py','freeze_v012.py',
        'runtime_review.py','review_pairs.py','review_audit.py','comparison_page.py','verify_review_player.cjs','reference_segments.py']]
    audit=dict(result='pass',version='0.12.0',ctest_count=14,shared_gain_pairs=4,unchanged_bench_cases=4,
        stereo_714_identical_sources=10,approved_media=media,preserved_baselines=history,audition_files=auditions,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(sources)},
        deliverables={name:sha(ROOT/name) for name in deliverables},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; reduced vehicle dynamics is verified, full timbre/state/transfer/physical dynamics/spatial listening incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.12.0',ctests=14,pairs=4,bench_unchanged=4,source_equality=10,history=history,goal='active'),indent=2))


if __name__=='__main__':main()
