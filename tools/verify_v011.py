"""Audit the main-bank spectrum repair without claiming vehicle realism."""
from pathlib import Path
from html.parser import HTMLParser
import json
from runtime_review import ROOT,sha
from reference_segments import catalog,checked_source
from review_audit import read_json as read,pair,frozen_baselines,device
import soundfile as sf
OUT=ROOT/'renders/v0.11.0'


def progress():
    full=read(ROOT/'research/goal_progress_v010.json')['full_objective_audit']
    full[1].update(status='Incomplete: actual principal bank-order handoff no longer has a code-boundary notch; low DNA remains unchanged. Subjective timbre, measured RPM/load spectra and acoustic transfer remain unaccepted.',evidence='research/V011试听.html; renders/v0.11.0/verification.json')
    full[2].update(status='Partial: canonical exterior segments and multi-hypothesis spacing observations with known-signal octave controls. Automatic spacing swaps during revs; it is not RPM/load or video-validated state telemetry.',evidence='references/analysis/order_families_v1/results.json')
    full[3].update(status='Ten independent sources remain identical in stereo and 7.1.4 exports. No new measured listener transfer or actual array listening.',evidence='renders/v0.11.0/drive_714_scene.json')
    full[4].update(status='Partial: driving/state/fuel/pressure controls remain identical while principal exhaust harmonics share a continuous source law. Torque/inertia, full weak-cycle components, pipes and calibrated start/stop remain incomplete.',evidence='src/core/exhaust_spectrum.c; src/core/high_orders.c; tests/test_spectral_continuity.c')
    result=dict(goal_status='active',review_version='0.11.0',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        implemented_this_iteration=['Canonical exterior harmonic-spacing hypotheses with explicit octave/subharmonic controls and no RPM default retuning',
            'Measured frozen V010 handoff defect; shared factory envelope and strong-bank continuation to remove the source-code boundary notch',
            'Five RPM/two-load emitted-source measurements, retained bank phase and unchanged low DNA/other templates/imported DNA',
            'Nine mixes plus three source pairs with common gain; driving and seven other objects unchanged; ten source objects identical across stereo/7.1.4',
            'Thirteen CTests, actual muted UI/preset/device and 24 browser switches, current GitHub V6 HEAD and preserved source history'],
        subjective_review='Pending: optional V011 listening question sent; no acceptance inferred.',
        evidence=dict(review='research/V011试听.html',implementation='research/V011排气谱形衔接.md',audit='renders/v0.11.0/workspace_audit.json'),
        full_objective_audit=full,remaining_work=['Subjective check of continuity, harshness and high-RPM body/detail',
            'RPM/load/state spectra, source-to-listener transfer and reference harmonic identity; automatic comb candidates are insufficient',
            'Physical torque/inertia, intake/exhaust pipes, weak full-cycle components and pressure-to-body coupling',
            'Calibrated stereo and physical 7.1.4 audition; keep full goal active'])
    (ROOT/'research/goal_progress_v011.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


def main():
    r=read(OUT/'verification.json');assert r['version']=='0.11.0' and r['seed']==48271
    for name,digest in r['files'].items():assert sha(OUT/name)==digest,name
    for name,digest in r['binaries'].items():assert sha(ROOT/'build-v011/Release'/name)==digest,name
    auditions={};assert len(r['cases'])==9 and len(r['isolated'])==3
    for name,takes in r['cases'].items():
        auditions.update(pair(OUT,{tag:takes[tag]['audition'] for tag in ['v010','v011']},['v010','v011'],
            raw={tag:OUT/f'{name}_{tag}.wav' for tag in ['v010','v011']}))
        assert (OUT/f'{name}_v010.csv').read_bytes()==(OUT/f'{name}_v011.csv').read_bytes()
        assert len(takes['unchanged_objects'])==7
        for file in takes['unchanged_objects']:
            assert (OUT/'stems'/file).read_bytes()==(OUT/'stems'/file.replace('_v010_','_v011_')).read_bytes()
    for takes in r['isolated'].values():auditions.update(pair(OUT,takes,['v010','v011']))
    assert (OUT/'ctest.log').read_bytes().count(b'Test Passed.')==13
    assert b'continuous_exhaust_spectrum' in (OUT/'ctest.log').read_bytes()
    device(r['device'],'0.11.0');assert r['device']==read(OUT/'ui_smoke.json')
    browser=read(OUT/'browser_qa.json');assert browser['result']=='pass' and browser['metadata_loads']==24 and browser['reference_metadata_loads']==2
    for profile in range(1,5):assert (OUT/f'compat_profile{profile}_v010.wav').read_bytes()==(OUT/f'compat_profile{profile}_v011.wav').read_bytes()
    for label in ['detail_zero','imported']:assert (OUT/f'compat_{label}_v010.wav').read_bytes()==(OUT/f'compat_{label}_v011.wav').read_bytes()
    assert r['handoff']['original_analysis_sha256']==sha(ROOT/'references/analysis/spectral_handoff_v1/results.json')
    for takes in r['handoff']['cases'].values():
        for item in takes.values():
            assert item['maximum_adjacent_step_orders25_29_db']<6 and item['max_orders15_25_change_db']<.002
            assert abs(item['new_order26_to25_db'])<1.6 and sha(ROOT/item['old_source'])==item['old_source_sha256']
    scene=read(OUT/'drive_714_scene.json');assert scene['dsp_version']=='0.11.0' and len(scene['objects'])==10
    assert scene['channels']==['FL','FR','FC','LFE','BL','BR','SL','SR','TFL','TFR','TBL','TBR']
    for obj in scene['objects']:
        path=OUT/obj['file'];assert sha(path)==obj['sha256'] and sf.info(path).subtype=='FLOAT'
        assert path.read_bytes()==(OUT/f'stems/drive_v011_{obj["name"]}.wav').read_bytes()
    obs=read(ROOT/'references/analysis/order_families_v1/results.json');assert len(obs['recordings'])==3
    for name,digest in obs['tools'].items():assert sha(ROOT/name)==digest,name
    for item in obs['recordings'].values():assert sha(ROOT/item['provenance']['master'])==item['provenance']['master_sha256']
    controls=obs['controls'];assert abs(controls['full_family']['estimated_spacing_hz']-52.3)<.5
    assert abs(controls['even_only']['estimated_spacing_hz']-104.6)<.5
    media={identity:checked_source(identity) for identity in ['A','B']}
    assert sha(ROOT/media['A']['video'])==media['A']['video_sha256']
    for name in ['A_exterior_low_rev','A_exterior_blips']:
        path=ROOT/catalog()['segments'][name]['existing_audition'];p=read(path.with_name(path.name+'.provenance.json'))
        assert sha(path)==p['output_sha256'] and not p['normalization'] and not p['denoise'] and sf.info(path).channels==2
    assert read(ROOT/'research/upstream_head_v011.json')['sha']=='ac2b37d8639027d79934a2023cf8d1d37d3b2f96'
    assert sha(ROOT/'research/upstream_v6/code/drive_model.js')=='28d6339bb6c308ed7f4d728d2c7f8e5c65f8fb869822b33c4c88c1f66b9ab759'
    assert sha(ROOT/'research/upstream/gen/v10_powertrain.gendsp')=='28be732d5d4c9497140562c89cd53cb3af5a82685ecd2945808d263767dd0584'
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key in ['src','href'] and not value.startswith(('http:','https:','#')):assert (ROOT/'research'/value).resolve().is_file(),value
    Links().feed((ROOT/'research/V011试听.html').read_text(encoding='utf-8'))
    preserved=frozen_baselines({f'v0.{v}.0':count for v,count in [(1,23),(2,64),(3,81),(4,99),(5,112),(6,161),(7,157),(8,182),(9,190),(10,205)]})
    progress()
    source=[ROOT/'CMakeLists.txt',*(ROOT/'src').rglob('*.c'),*(ROOT/'src').rglob('*.h'),*(ROOT/'tests').glob('*.c')]
    files=['README.md','AGENTS.md','build.ps1','Launch.cmd','research/V011试听.html','research/V011排气谱形衔接.md',
        'research/goal_progress_v011.json','research/upstream_head_v011.json','references/segments_v1.json',
        'references/analysis/spectral_handoff_v1/results.json','references/analysis/spectral_handoff_v1/handoff.png',
        'renders/v0.9.0/dna_check/known_steady_harmonics.dna']
    files+=['tools/'+n for n in ['harmonic_family.py','analyze_reference_orders.py','inspect_spectral_handoff.py','render_v011_review.py',
        'make_v011_review.py','verify_v011.py','freeze_v011.py','review_audit.py','reference_segments.py','runtime_review.py','review_pairs.py',
        'comparison_page.py','verify_review_player.cjs','capture_preview.py']]
    files+=[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'references/analysis/order_families_v1').iterdir() if p.is_file()]
    audit=dict(result='pass',version='0.11.0',ctest_count=13,shared_gain_pairs=12,unchanged_driving_cases=9,unchanged_other_objects_per_case=7,
        other_templates_bit_identical=4,stereo_714_identical_sources=10,approved_media=media,preserved_baselines=preserved,audition_files=auditions,
        source_code={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(source)},
        deliverables={name:sha(ROOT/name) for name in files},
        rendered_artifacts={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='workspace_audit.json'},
        goal_status='active; continuity is verified, high-RPM timbre/transfer/dynamics and actual spatial listening remain incomplete')
    (OUT/'workspace_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',version='0.11.0',ctests=13,common_gain_pairs=12,source_equality=10,preserved=preserved,goal='active'),indent=2))


if __name__=='__main__':main()
