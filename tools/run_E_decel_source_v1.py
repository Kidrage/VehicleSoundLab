"""Fit only qualified fixed-time E slowing-context voices with unchanged C kernels."""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for name in ('workspace', 'out', 'dna-probe', 'detail-probe'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from drive_evidence_v1.sources import read
from decel_source_v1.aperture import extract
from decel_source_v1.checks import run as known_controls
from sound_dna.windowed import estimate
from sound_dna.profile import export
from idle_texture_v1.profile import attenuate
from stationary_recipe_v1.parameters import compile_detail, encode
from resonant_detail_v1.controls import run as detail_controls
from resonant_detail_v1.voice import render as detail_oracle
from residual_osc_v1.spectrum import matrices, error

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', inputs={}, sources={}, commands=[], accepted=[], rejected=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


def command(argv, label):
    result = subprocess.run(list(map(str, argv)), cwd=repo, capture_output=True, timeout=180)
    log = a.out/(label+'.log')
    log.write_bytes(result.stdout+result.stderr)
    r['commands'].append(dict(argv=list(map(str, argv)), exit_code=result.returncode,
                              log=log.name, sha256=sha(log)))
    save(a.out/'report.json', r)
    if result.returncode:
        raise RuntimeError(log)


try:
    names = ['tools/run_E_decel_source_v1.py', 'research/E_decel_source_v1_plan.json',
             'tools/research_archive_v1.py', 'tools/drive_evidence_v1/sources.py',
             'tools/exterior_clock_v1/warp.py', 'tools/idle_texture_v1/profile.py',
             'tools/stationary_recipe_v1/parameters.py', 'tools/residual_osc_v1/spectrum.py']
    for package in ('decel_source_v1', 'sound_dna', 'resonant_detail_v1'):
        names += [x.relative_to(repo).as_posix() for x in (repo/'tools'/package).glob('*.py')]
    for name in sorted(set(names)):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    plan = load(consume(repo/'research/E_decel_source_v1_plan.json'))
    kernel = load(consume(repo/'research/resonant_detail_v1_plan.json'))
    # Complete analytic controls before any new real-waveform read.
    r['known_controls_before_source'] = known_controls(plan)
    r['detail_controls_before_source'] = detail_controls(kernel)
    save(a.out/'report.json', r)
    parent = a.workspace/'baselines/shift_repeat_v1'
    manifest = load(consume(parent/'manifest.json'))
    relative = 'evidence/exploration1/report.json'
    frozen = parent/relative
    assert sha(consume(frozen)) == next(v['sha256'] for v in manifest['files'] if v['path'] == relative)
    observation = load(frozen)
    family = next(v for v in observation['families']
                  if v['start'] == plan['clock_selection']['start'] and
                  v['anchor_root'] == plan['clock_selection']['anchor_root'])
    assert family['status'] == 'connected_observed_family' and family['reference_multiple'] == 5
    clock = [v for v in family['rows'] if plan['visual_scope_seconds'][0] <= v['seconds'] <= plan['visual_scope_seconds'][1]]
    save(a.out/'consumed_clock.json', dict(family=family, selected_rows=clock))
    audio, provenance = read(a.workspace, plan['source'], plan['use'])
    r['source'] = provenance
    # Later approved sources changed the registry document, not this segment.
    # Require every source/sample/context field to match the frozen input;
    # retain both catalog identities instead of pretending they are identical.
    previous = observation['provenance']
    r['previous_catalog_sha256'] = previous['catalog_sha256']
    assert {k: v for k, v in provenance.items() if k != 'catalog_sha256'} == {
        k: v for k, v in previous.items() if k != 'catalog_sha256'}
    registry = load(consume(a.workspace/'references/segments_v1.json'))['sources']['E']
    for key in ('raw', 'master'):
        consume(a.workspace/registry[key])
    for executable in (a.dna_probe, a.detail_probe):
        consume(executable)
    for number, case in enumerate(plan['cases']):
        folder = a.out/case['name']
        folder.mkdir()
        normalized, where, extraction = extract(audio, provenance['seconds'][0], clock,
                                                 case['center_seconds'], plan)
        root = extraction['root_hz']
        sf.write(folder/'normalized.wav', normalized, 48000, subtype='FLOAT')
        np.savez_compressed(folder/'coordinates.npz', source_seconds=where)
        first, stop = [round((t-provenance['seconds'][0])*48000)
                       for t in extraction['phase']['source_seconds']]
        sf.write(folder/'raw_source.wav', audio[first:stop], 48000, subtype='FLOAT')
        model, statistics = estimate(normalized, plan['harmonics'], plan['components'])
        ratio = Fraction(46.875/root).limit_denominator(10000)
        reference = signal.resample_poly(normalized, ratio.numerator, ratio.denominator,
                                         axis=0, window=('kaiser', 8.6))
        sf.write(folder/'reference.wav', reference, 48000, subtype='FLOAT')
        row = dict(case=case, **extraction, statistics=statistics,
                   resample_ratio=[ratio.numerator, ratio.denominator])
        save(folder/'extraction.json', row)
        minimum = min(v for values in extraction['heldout_coherence'].values() for v in values)
        if statistics['observation_frames'] < plan['gates']['minimum_observations'] or minimum <= plan['gates']['heldout_carrier_coherence']:
            r['rejected'].append(dict(**row, reason='Original aperture/heldout gate failed; no profile or synthesized candidate'))
            save(a.out/'report.json', r)
            print(dict(name=case['name'], rejected=True, heldout=extraction['heldout_coherence']), flush=True)
            continue
        assert root*plan['harmonics']*1.1 < 21600
        export(folder/'voice.model', model, root)
        modified, gain = attenuate(model, root, plan['replacement_power'], plan['transition_hz'])
        export(folder/'withdraw35.model', modified, root)
        dna = {}
        for label, path in [('original', folder/'voice.model'), ('withdraw35', folder/'withdraw35.model')]:
            command([a.dna_probe, path, folder/(label+'.wav'), plan['seconds'], 1, 1, 1], f'DNA_{number}_{label}')
            dna[label], rate = sf.read(folder/(label+'.wav'), always_2d=True)
            assert rate == 48000
        detail = compile_detail(reference, dna['withdraw35'][plan['crop_frames']:], kernel)
        encode(folder/'detail.rdetail', detail, root, kernel['warmup_frames'])
        row.update(detail_model=detail, renders=[])
        r['accepted'].append(row)
        for seed in plan['seeds']:
            warm = kernel['warmup_frames']
            raw = folder/f'detail_{seed}.f64'
            command([a.detail_probe, folder/'detail.rdetail', raw, warm+plan['seconds']*48000,
                     seed, -warm*root/48000], f'detail_{number}_{seed}')
            values = np.fromfile(raw, dtype='<f8').reshape(-1, len(detail['filters'])+2)[warm:]
            if seed == plan['seeds'][0]:
                expected = detail_oracle(detail['filters'], plan['seconds']*48000, seed, kernel)
                maximum = float(abs(expected-values[:, 2:]).max())
                assert maximum < plan['gates']['C_detail_oracle_FS']
                row['C_detail_oracle_FS'] = maximum
            mixed = dna['withdraw35']+values[:, :2]
            peak = float(abs(mixed).max())
            assert np.isfinite(mixed).all() and peak*plan['output_gain'] < plan['gates']['maximum_peak_after_gain']
            metrics = error(matrices(reference), matrices(mixed[plan['crop_frames']:]))
            maximum = max(abs(v) for band in metrics for v in band['power_delta_db'])
            sf.write(folder/f'candidate_{seed}.wav', mixed, 48000, subtype='FLOAT')
            sf.write(folder/f'detail_{seed}.wav', values[:, :2], 48000, subtype='FLOAT')
            row['renders'].append(dict(seed=seed, peak_FS=peak, maximum_LR_band_power_error_db=maximum, metrics=metrics))
            save(a.out/'report.json', r)
            assert maximum < plan['gates']['maximum_LR_band_power_error_db'], (case, seed, maximum)
        save(folder/'model.json', row)
        print(dict(name=case['name'], root_hz=root, heldout=extraction['heldout_coherence']), flush=True)
    r.update(result='fixed_centers_checked', accepted_count=len(r['accepted']), rejected_count=len(r['rejected']),
             human_accepted=False, runtime_changed=False, physical_deceleration_model=False,
             new_engines=0, room=False, recorded_timeline=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
