"""One declared E evaluation, after strict fractional-clock qualification."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--validated',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from multicarrier_clock_v1.coarse import track
from fractional_clock_v1.coordinate import warp
from fractional_clock_v1.phase import refine,diagnostics
from fractional_clock_v1.measure import moments,coherent_moments,compare


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.fractional-source-evaluation/1',result='running',sources={},
    model_exported=False,real_C_render_executed=False,runtime_modified=False,vehicle_timbre_accepted=False,source_audio_read=False)
try:
    plan_path=repo/'research/fractional_clock_v1_plan.json'
    plan=load(plan_path)
    for source in (Path(__file__),plan_path):
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    validated=load(args.validated/'report.json')
    assert validated['result']=='passed' and validated['real_source_permitted'], 'Independent fractional-clock qualification incomplete; no source read allowed'
    assert sha(plan_path)==validated['plan_sha256'] and plan['require_coherent_grid_power_and_stereo']
    assert [item['case'] for item in validated['cases']]==plan['fixtures']
    assert all(item['passed'] and (item['case'].get('negative') or item.get('coherent_oracle')) for item in validated['cases'])
    for name,digest in validated['sources'].items():
        assert sha(repo/name)==sha(args.validated/'exact_sources'/name)==digest
    report['validation_report_sha256']=sha(args.validated/'report.json')
    original=load(args.workspace/'references/analysis/multicarrier_clock_v1/E_source1/report.json')
    case=original['source_case']
    assert original['result']=='source_phase_rejected' and case['seconds']==plan['real_case']['seconds']==[5.2,7.8]
    assert case['initial_root_hz']==32.8
    report.update(original_rejection_sha256=sha(args.workspace/'references/analysis/multicarrier_clock_v1/E_source1/report.json'),case=case)
    sources=[Path(__file__),plan_path,repo/'references/segments_v1.json',repo/'tools/drive_evidence_v1/sources.py',
        repo/'tools/multicarrier_clock_v1/coarse.py',repo/'tools/state_colour_v2/clock.py',repo/'tools/exterior_clock_v1/warp.py']
    sources+=list((repo/'tools/fractional_clock_v1').glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    audio,provenance=read(args.workspace,'E_exterior_stationary_intro_context','exterior_spectral_observation')
    report['source_audio_read']=True
    assert provenance['source']=='E' and provenance['master_sha256']==original['input']['master_sha256']
    report['input']=provenance
    observed_dir=args.workspace/'references/analysis/E_low_state_v1/observe2'
    observed_report=load(observed_dir/'report.json')
    entry=observed_report['segments'][case['observation']]
    measured_path=observed_dir/case['observation']/'observations_80ms.npz'
    assert sha(measured_path)==entry['observations']['80']['observations_sha256']
    report['measured_observation_sha256']=sha(measured_path)
    with np.load(measured_path,allow_pickle=False) as archive:
        measured={key:archive[key] for key in archive.files}
    path=track(measured,*case['seconds'],case['initial_root_hz'],plan['coarse'])
    save(args.out/'coarse.json',path)
    report['track_status']=path['status']
    report['coarse_policy']='Same declared80ms observations and lattice, with the currently qualified support-constrained smoother; old8Hz coordinate and rejection remain frozen'
    if not path['rows']:
        report['result']='source_coarse_rejected'
    else:
        times=np.array([row['seconds'] for row in path['rows']])
        roots=np.array([row['root_hz'] for row in path['rows']])
        normalized,positions,cutoff=warp(audio,provenance['seconds'][0],times,roots,*case['seconds'],plan['coordinate'])
        np.savez_compressed(args.out/'initial_coordinates.npz',source_seconds=positions)
        try:
            normalized,positions,phase=refine(audio,provenance['seconds'][0],normalized,positions,cutoff,plan['coordinate'],plan['phase'])
            cycle=plan['coordinate']['samples_per_coarse_cycle']
            base=float(np.median(1/(cycle*np.diff(positions))))
            split=len(normalized)//2
            halves=(normalized[:split],normalized[split:])
            checks=[diagnostics(part,cycle,plan['heldout_orders'],plan['heldout_projection_cycles'],plan['rules'])
                for part in (normalized,*halves)]
            counts=[len(part)//(cycle*plan['coherent_power_window_coarse_cycles']) for part in halves]
            delta=compare(moments(halves[0],cycle,base,plan['bands_hz'],plan['power_window_coarse_cycles']),
                moments(halves[1],cycle,base,plan['bands_hz'],plan['power_window_coarse_cycles']))
            coherent=compare(coherent_moments(halves[0],cycle,base,plan['bands_hz'],plan['coherent_power_window_coarse_cycles'],5),
                coherent_moments(halves[1],cycle,base,plan['bands_hz'],plan['coherent_power_window_coarse_cycles'],5))
            qualified=bool(all(item['passed'] for item in checks) and min(counts)>=6 and
                max(delta['maximum_band_power_error_db'],coherent['maximum_band_power_error_db'])<=3 and
                max(delta['maximum_complex_correlation_error'],coherent['maximum_complex_correlation_error'])<=.2)
            np.savez_compressed(args.out/'coordinates_and_stereo.npz',source_seconds=positions,stereo=normalized)
            report.update(result='source_phase_measured_no_model_export',phase=phase,display_coarse_root_hz=base,
                independent_checks_full_first_last=checks,nonoverlapping_fullgrid_windows_per_half=counts,
                required_windows_per_half=6,stationary_model_qualified=qualified,
                half_total_moments=delta,half_coherent_moments=coherent,
                retained_source_seconds=[float(positions[0]),float(positions[-1])],source_cutoff_hz=phase['source_cutoff_hz'])
        except ValueError as exc:
            report.update(result='source_phase_rejected',reason=str(exc),stationary_model_qualified=False)
    report['limits']=['Acoustic coordinate only; fifth-grid identity is not physical RPM or verified warm idle/load',
        'Clock qualification does not authorize sparse/wider C model export; no candidate audio is generated here',
        'Six independent four-full-grid-period windows per half are required before a stationary statistical model',
        'Original E rejection, accepted moving35, old C/model/runtime and pending media questions remain unchanged']
    print(json.dumps({key:report.get(key) for key in ('result','reason','track_status','display_coarse_root_hz','nonoverlapping_fullgrid_windows_per_half','stationary_model_qualified')}),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
