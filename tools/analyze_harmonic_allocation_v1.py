"""Qualify cross-window shape and coherent/residual allocation before new fits."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from harmonic_allocation_v1.observe import coefficients, band_statistics, shape_motion, compare
from harmonic_allocation_v1.controls import cases, fraction_control
from residual_osc_v1.spectrum import matrices, error

args.out.mkdir(parents=True, exist_ok=False)
plan_path = repo/'research/harmonic_allocation_v1_plan.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
paths = [Path(__file__), plan_path, repo/'tools/drive_evidence_v1/sources.py',
         repo/'tools/residual_osc_v1/spectrum.py', *sorted((repo/'tools/harmonic_allocation_v1').glob('*.py'))]
for path in paths:
    dest = args.out/'exact_sources'/path.relative_to(repo); dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
report = dict(schema='vsl.harmonic-allocation-analysis/1', result='running', observations=[],
              base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
              source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths}, input_sha256={})
(args.out/'metadata.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')


def bound(root, name):
    manifest = root/'manifest.json'
    expected = next(r['sha256'] for r in json.loads(manifest.read_text(encoding='utf-8'))['files'] if r['path']==name)
    assert sha(root/name)==expected, name
    report['input_sha256'][str(root/name)] = expected
    report['input_sha256'][str(manifest)] = sha(manifest)
    return root/name


def observe(name, audio):
    rows = []; arrays = {}; pairs = []
    for origin in plan['origins_frames']:
        slow_by_window = {}
        for config in plan['windows']:
            centers, starts, z, dft_error = coefficients(audio, plan, config, origin)
            assert dft_error < plan['tolerances']['direct_DFT_relative'], (name, config, dft_error)
            power, fraction, agreement = band_statistics(z, plan)
            motion, slow, projection_error, slow_hz = shape_motion(power, plan)
            assert projection_error < plan['tolerances']['projection_relative'], (name, projection_error)
            slow_by_window[config['name']] = slow
            key = config['name']+'_'+str(origin)
            arrays.update({key+'_centers':centers, key+'_power':power, key+'_slow_shape':slow,
                           key+'_coherent_fraction':fraction, key+'_split_agreement':agreement})
            shape_rms = float(np.sqrt(np.mean(motion**2)))
            if name=='known_stationary_OSC':
                assert shape_rms < plan['tolerances']['constant_shape_db'], shape_rms
                assert np.max(abs(fraction-1)) < plan['tolerances']['known_fraction_error']
            row = dict(window=config['name'], origin_frame=origin, frames=len(z),
                       center_seconds=[float(centers[0]/48000),float(centers[-1]/48000)],
                       mean_central_harmonic_power_LR=power.mean(axis=0).tolist(),
                       coherent_fraction_LR=fraction.tolist(), split_half_agreement_LR=agreement.tolist(),
                       shape_motion_rms_db_LR=np.sqrt(np.mean(motion**2,axis=(0,1))).tolist(),
                       slow_shape_rms_db_LR=np.sqrt(np.mean(slow**2,axis=(0,1))).tolist(),
                       slow_bins_hz=slow_hz.tolist(), direct_DFT_relative_error=dft_error,
                       projection_relative_error=projection_error)
            if name=='known_common_gain':
                row['common_gain_shape_gate'] = dict(measured_rms_db=shape_rms,
                    threshold_db=plan['tolerances']['common_gain_shape_db'],
                    passed=shape_rms < plan['tolerances']['common_gain_shape_db'])
            if name=='known_shape_AM':
                signed = (-1.)**np.arange(len(plan['bands']))
                truth = (20/np.log(10)*plan['known_AM_log_depth']*
                         np.sin(2*np.pi*plan['known_AM_hz']*centers/48000))[:,None,None]*signed[None,:,None]
                # Pass the exact known band powers through the same projection only.
                _, expected, _, _ = shape_motion(10**(np.broadcast_to(truth,power.shape)/10), plan)
                e = float(np.sqrt(np.mean((slow-expected)**2)))
                row['known_shape_AM_error_db'] = e
                row['known_shape_AM_gate'] = dict(threshold_db=plan['tolerances']['shape_AM_error_db'],
                    passed=e < plan['tolerances']['shape_AM_error_db'])
            rows.append(row)
        pairs.append(dict(origin_frame=origin, comparisons=compare(slow_by_window)))
    path = args.out/(name+'.npz'); np.savez_compressed(path, **arrays)
    report['observations'].append(dict(name=name, input_frames=len(audio), configurations=rows,
                                       cross_window_shape=pairs, arrays_sha256=sha(path)))
    print(json.dumps(dict(name=name, origin0=[dict(window=r['window'],slow_db=r['slow_shape_rms_db_LR'],
        coherent_fraction_median=float(np.median(r['coherent_fraction_LR']))) for r in rows if r['origin_frame']==0])),flush=True)


try:
    prior = args.workspace/'baselines/residual_motion_v1'
    reference, rate = sf.read(bound(prior,'evidence/fit1/reference.wav'), always_2d=True)
    base, base_rate = sf.read(bound(prior,'evidence/fit1/accepted_pair.wav'), always_2d=True)
    assert rate==base_rate==plan['sample_rate'] and len(reference)==58424
    prior_texture = args.workspace/'baselines/temporal_texture_v1'
    archive = np.load(bound(prior_texture,'evidence/magnitude1/candidate_moments.npz'))
    model = {k:archive[k] for k in ('rms','basis','rho','root','residual_rho')}
    phase = archive['fixed_phase']
    report['fraction_controls'] = [fraction_control(len(reference),plan,c,o)
        for c in plan['windows'] for o in plan['origins_frames']]
    for row in report['fraction_controls']:
        assert row['analytic_fraction_error'] < plan['tolerances']['known_fraction_error']
        assert row['known_clock_corrected_fraction'] > plan['tolerances']['known_detune_corrected_fraction_min']
        assert row['nominal_fraction'] < plan['tolerances']['known_detune_raw_fraction_max']
    for name, audio in cases(model, phase, len(reference), plan): observe(name, audio)
    observe('fixed_A_reference', reference)
    for seconds in plan['candidate_block_starts_seconds']:
        start = round(seconds*48000)
        observe('accepted_DNA_LF_'+str(seconds), base[start:start+len(reference)])
    target = matrices(reference)
    represented = matrices(base[24000:])
    report['actual_C_power_budget'] = dict(reference=target, represented=represented, errors=error(target,represented),
        negative_diagonal_bands=[a['hz'] for a,b in zip(target,represented) if min(np.array(a['power'])-np.array(b['power']))<0],
        scope='Actual frozen accepted C DNA+LF, not the sum of central-bin estimates. Welch mean, no refit/gain compensation.')
    catalog_path = args.workspace/'references/segments_v1.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    source = catalog['sources']['A']
    report['input_sha256'][str(catalog_path)] = sha(catalog_path)
    for kind in ('raw','master'):
        path = args.workspace/source[kind]
        assert sha(path)==source[kind+'_sha256']
        report['input_sha256'][str(path)] = source[kind+'_sha256']
    with sf.SoundFile(args.workspace/source['master']) as stream:
        assert stream.samplerate==48000 and stream.channels==2
        stream.seek(round(316.10*48000))
        raw = stream.read(round((317.25-316.10)*48000),always_2d=True)
    def stereo_difference(audio):
        return float(np.sqrt(np.mean((audio[:,0]-audio[:,1])**2))/max(float(np.sqrt(np.mean(audio**2))),1e-30))
    report['stereo_scope'] = dict(A_master_seconds=[316.10,317.25],
        raw_master_LminusR_relative_rms=stereo_difference(raw),
        normalized_reference_LminusR_relative_rms=stereo_difference(reference),
        accepted_pair_LminusR_relative_rms=stereo_difference(base),
        interpretation='These measurements establish observed channel difference only; no physical source assignment or stereo-widening validation.')
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream: index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index: assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repo/accepted['model'])==accepted['model_sha256']
    assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
    shape_gates = [r[key]['passed'] for ob in report['observations'] for r in ob['configurations']
                   for key in ('common_gain_shape_gate','known_shape_AM_gate') if key in r]
    report.update(result='diagnostics_completed',shape_extraction_qualified=all(shape_gates),
        c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        accepted_models_unchanged=True,runtime_changes=False,new_fit=False,human_accepted=False,
        allocation_decision='Do not use |mean complex coefficient|^2/E|coefficient|^2 as an automatic harmonic-to-cloud power split: a known pure detuned tone is a counterexample.',
        limits=[plan['scope'],'Central-bin coherent fractions are descriptive and finite-window biased, not physical noise fractions',
            'Cross-window agreement alone cannot distinguish actual AM from stationary noise/window beating',
            'One short normalized A block cannot identify stable sub-Hz statistics, RPM/load or propagation',
            'Known exact clock correction validates the control only; no real clock was estimated or corrected',
            'C observations share one continuous realization and are not independent engine recordings',
            'Power budgets do not qualify naturalness or identify intake/exhaust/mechanical sources',
            'Existing listening pending; no new candidate/default/UI/driver/spatial adoption'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],observations=len(report['observations']),fraction_controls=len(report['fraction_controls']))),flush=True)
