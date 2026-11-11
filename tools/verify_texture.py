"""Audit the completed texture investigation and preserve frozen runtimes."""
import csv
import json
import shutil
import platform
from pathlib import Path
from runtime_review import ROOT,sha
from reference_segments import read_segment
from review_audit import frozen_baselines
import numpy as np
import scipy
import soundfile as sf

OUT=ROOT/'references/analysis/texture_v1'
COUNTS=dict(zip([f'v0.{n}.0' for n in range(1,16)],
    [23,64,81,99,112,161,157,182,190,205,189,156,167,175,174]))


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    if (OUT/'verification.json').exists():raise SystemExit('Preserve completed texture verification.')
    data=read(OUT/'results.json');probes=read(OUT/'probes.json');extra=read(OUT/'supplement.json')
    for document in [data,probes,extra]:
        for name,digest in document['files'].items():assert sha(OUT/name)==digest,name
    assert extra['primary_results_sha256']==sha(OUT/'results.json')
    assert extra['tool_sha256']==sha(ROOT/'tools/finalize_texture.py')
    for path,digest in probes['linked_inputs'].items():assert sha(ROOT/path)==digest
    assert len(probes['cases'])==len(data['runtime'])==20
    assert sum(p['frozen_compatibility_pcm_sha256'] is not None for p in probes['cases'].values())==4
    states={}
    for name,params in probes['cases'].items():
        prefix=OUT/'runtime'/name
        info=sf.info(prefix.with_suffix('.wav'));assert info.subtype=='FLOAT' and info.channels==2 and info.frames==288000
        with prefix.with_suffix('.csv').open() as f:
            rows=[r for r in csv.DictReader(f) if 2.5<=float(r['seconds'])<=5.8]
        assert len(rows)>500 and {r['lifecycle'] for r in rows}=={'RUNNING'} and {r['operating'] for r in rows}=={'FREE REV'}
        max_rpm_error=max(abs(float(r['rpm'])-params['rpm']) for r in rows)
        assert max_rpm_error<.01 and max(abs(float(r['load'])-params['load']) for r in rows)<1e-6
        states[name]=dict(max_rpm_error=max_rpm_error,air_gain_range=[min(float(r['air_gain']) for r in rows),max(float(r['air_gain']) for r in rows)])
        stems=list(prefix.parent.glob(prefix.name+'_source_*.wav'));assert len(stems)==10
        for stem in stems:
            si=sf.info(stem);assert si.subtype=='FLOAT' and si.channels==1 and si.frames==288000
        if params['frozen_compatibility_pcm_sha256']:
            assert sha(prefix.with_name(name+'_compat.wav'))==sha(prefix.with_name(name+'_frozen.wav'))==params['frozen_compatibility_pcm_sha256']
    provenance={}
    uses={'A_low':'exterior_spectral_observation','A_blips':'exterior_dynamic_observation',
        'A_moving':'exterior_dynamic_observation','B_cabin':'interior_channel_observation'}
    for name,row in data['references'].items():
        x,rate,p=read_segment(row['provenance']['segment_id'],uses[name]);assert p==row['provenance']
        assert rate==48000 and x.shape[1]==2;provenance[name]=p
        for report in row['measurements'].values():
            for band in report['bands']:
                assert max(band['below_minus100_dbfs_fraction'].values())==0
    control=data['controls'];assert control['checks']['max_gain_invariance_error']<1e-10
    assert control['checks']['channel_swap_exact'] and control['checks']['warp_channel_swap_exact']
    assert control['checks']['resampler_14khz_waveform_error_db']<-50
    analytic=extra['analytic_controls'];assert analytic['status']=='pass'
    for check in analytic['anti_phase_tone_power'].values():assert max(abs(v-check['expected_dbfs']) for v in check['observed_dbfs'])<.002
    for check in analytic['exponential_pitch_peaks']:assert abs(check['expected_hz']-check['peak_hz'])<1
    assert len(analytic['pitch_error_sensitivity'])==4
    normalized=[]
    for run in data['reference_compensation']['runs'].values():
        assert run['path']['support_fraction']>.99
        assert run['metadata']['max_input_time_step_per_output_time']<=1
        assert run['metadata']['interpolation']['upsampling']==16
        normalized.append(run['measurements']['12_cycles']['bands'][2]['channels']['L']['whitened_flatness']['median'])
    assert len(normalized)==3 and max(normalized)-min(normalized)<.01
    # Engineering source observation; not a measured vehicle fit or optimum.
    balance=[r for r in extra['source_balance'] if r['load']==.85]
    assert max(r['air_power_sum_dbfs'] for r in balance)-min(r['air_power_sum_dbfs'] for r in balance)<.1
    drift=balance[-1]['air_to_exhaust_db']-balance[0]['air_to_exhaust_db'];assert -5.1<drift<-4.7
    for name in data['runtime']:
        if name.endswith('_full') and '_load85_' in name:assert states[name]['air_gain_range']==[.0952,.0952]
    # Current source/launch/binaries unchanged; README merely gains a research link.
    audit=read(ROOT/'renders/v0.15.0/workspace_audit.json')
    for name,digest in audit['source_code'].items():assert sha(ROOT/name)==digest,name
    for name in ['Launch.cmd','build.ps1','AGENTS.md']:assert sha(ROOT/name)==audit['deliverables'][name]
    runtime_report=read(ROOT/'renders/v0.15.0/verification.json')
    for name,digest in runtime_report['binaries'].items():assert sha(ROOT/'build-v015/Release'/name)==digest
    assert (ROOT/'renders/v0.15.0/ctest.log').read_bytes().count(b'Test Passed.')==17
    history=frozen_baselines(COUNTS)
    assert sha(ROOT/'research/upstream/gen/v10_powertrain.gendsp')==data['upstream']['snapshot_sha256']
    assert read(ROOT/'research/upstream_snapshot.json')['revision']==data['upstream']['revision']
    (OUT/'bin').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'build-research-texture/Release/texture_probe.exe',OUT/'bin/texture_probe.exe')
    progress=read(ROOT/'research/goal_progress_v015.json')
    progress.update(analysis_version='texture_v1',previous_goal_turn_classification='progress',this_goal_turn_classification='progress',
        runtime_changes=False,implemented_this_iteration=[
            '20 float32 and ten-source frozen V015 bench probes; four PCM control renders exact with frozen V015',
            'Per-channel spectral fine structure with resolution, colour and gain controls',
            'Common stereo observed-ridge compensation; analytic frequency/power and interpolation validation',
            'Canonical approved A/B observations, three-window ridge sensitivity and known pitch-error stress tests',
            'Identified nearly constant high-frequency air source at fixed load while exhaust source grows with RPM'],
        evidence=dict(report='research/高频纹理与周期补偿V1.md',results='references/analysis/texture_v1/results.json',verification='references/analysis/texture_v1/verification.json'),
        next_algorithm_candidate='Independent bounded RPM/load/state control of tailpipe airflow texture; engineering flow proxy first, explicit fixed-take listening before adopting new voicing. No fit to flatness/noise fractions.',
        subjective_review='No acceptance inferred; runtime V015 and pending sound/array listening remain unchanged.')
    progress['full_objective_audit'][1]['status']='Incomplete: high-frequency fine structure and existing air/exhaust RPM balance now measured in frozen V015; no matched reference RPM/load, physical source separation or subjective realism acceptance.'
    progress['full_objective_audit'][1]['evidence']='research/高频纹理与周期补偿V1.md; references/analysis/texture_v1/verification.json'
    (ROOT/'research/goal_progress_texture_v1.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    sources=['tools/'+name for name in ['texture_metrics.py','pitch_warp.py','render_texture_probes.py','analyze_texture.py','finalize_texture.py','verify_texture.py']]
    sources+=['tools/texture_probe/CMakeLists.txt','tools/texture_probe/probe.c','tools/reference_segments.py','tools/ridge_tracks.py']
    documents=['research/高频纹理与周期补偿V1.md','research/goal_progress_texture_v1.json','references/segments_v1.json','README.md']
    result=dict(result='pass',analysis_version='texture_v1',runtime_version='0.15.0',runtime_changes=False,
        runtime_audit_sha256=sha(ROOT/'renders/v0.15.0/workspace_audit.json'),
        ctests='Previous 17 passing CTests preserved; no C runtime change or repeated device test.',
        unchanged_runtime_source_count=len(audit['source_code']),unchanged_binaries=runtime_report['binaries'],
        probe_cases=20,source_stems=200,frozen_pcm_comparisons=4,source_states=states,
        reference_provenance=provenance,normalized_reference_flatness=normalized,
        air_exhaust_relative_drift_db=drift,history=history,
        environment=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
        tools={name:sha(ROOT/name) for name in sources},documents={name:sha(ROOT/name) for name in documents},
        files={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='verification.json'},
        goal_status='active: texture evidence changed next engineering action; full sound, car-specific physics and actual array acceptance incomplete')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='pass',analysis='texture_v1',runtime='0.15.0 unchanged',probe_cases=20,
        source_stems=200,air_exhaust_drift_db=drift,reference_normalized_flatness=normalized,history=history),indent=2))


if __name__=='__main__':main()
