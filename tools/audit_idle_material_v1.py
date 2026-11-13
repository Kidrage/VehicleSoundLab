"""Independently inspect native band powers and actual idle-state coverage."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools'/x) for x in ('ipm_deps', 'qp_deps', 'python_deps')]
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.idle-material-audit/1', result='running', sources={}, observations=[],
    common_phase_fit=False, new_DNA=False, runtime_changed=False)
try:
    parent = args.workspace/'references/analysis/idle_material_v1/observe2'
    observed = load(parent/'report.json'); assert observed['result'] == 'four_raw_contexts_and_actual_idle_coverage_extracted'
    sources = {Path(__file__)}
    for name, digest in observed['sources'].items():
        assert sha(repo/name) == sha(parent/'exact_sources'/name) == digest
        sources.add(repo/name)
    for path in sources:
        rel = path.relative_to(repo); dest = args.out/'exact_sources'/rel
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        r['sources'][rel.as_posix()] = sha(path)
    r['parent_report_sha256'] = sha(parent/'report.json')
    assert observed['observations_sha256'] == sha(parent/'observations.npz')
    data = np.load(parent/'observations.npz'); bands = observed['bands_hz']; n = 24000; rate = 48000
    catalog = load(args.workspace/'references/segments_v1.json')
    assert observed['catalogue_sha256'] == sha(args.workspace/'references/segments_v1.json')
    for item in observed['inventory']:
        assert sha(args.workspace/item['raw']) == item['raw_sha256'] and sha(args.workspace/item['master']) == item['master_sha256']
    for path, digest in observed['runtime_inputs'].items():
        assert sha(args.workspace/path) == digest
    for item in observed['observations']:
        key = item['id']; array_key = 'runtime_audio' if key == 'runtime_full_recipe_idle' else key+'_audio'
        audio = data[array_key]
        if key == 'runtime_full_recipe_idle':
            file = args.workspace/'references/analysis/full_recipe_drive_v1/verify1/full_pedals/recorded.wav'
            first, stop = observed['runtime']['frame_interval']
        else:
            source = catalog['sources'][item['provenance']['source']]
            file = args.workspace/source['master']; first, stop = [round(t*rate) for t in item['source_seconds']]
        with sf.SoundFile(file) as stream:
            stream.seek(first); raw = stream.read(stop-first, dtype='float64', always_2d=True)
        assert np.array_equal(audio, raw)
        powers = []; maximum = 0.
        for index in range(item['tiles']):
            tile = audio[index*n:(index+1)*n]
            frequency, density = signal.periodogram(tile, fs=rate, window='hann', detrend=False, axis=0, scaling='density')
            power = np.array([density[(frequency >= lo)&(frequency < hi)].sum(axis=0)*rate/n for lo,hi in bands])
            saved = np.array(item['per_tile_power'][index])
            normalized_error = float(np.linalg.norm(power-saved)/max(np.linalg.norm(saved), 1e-300))
            assert normalized_error <= 1e-12
            maximum = max(maximum, normalized_error); powers.append(power)
        mean = np.mean(powers, axis=0)
        fractions = mean/mean.sum(axis=0)[None, :]
        assert np.max(abs(fractions-np.array(item['fraction_of_mean_band_power']))) <= 1e-12
        r['observations'].append(dict(id=key, exact_native_source_slice=True, tiles=item['tiles'],
            maximum_periodogram_relative_vector_error=maximum))
    # Literal rectangular DFT of every measured bin for one real source tile
    # and the runtime tile: no FFT/Welch call in this independent path.
    literal = []
    for key in ('F2_tailpipe_audio', 'runtime_audio'):
        audio = data[key][:n]; time = np.arange(n); window = .5-.5*np.cos(2*np.pi*time/n)
        weighted = audio*window[:, None]; selected = np.arange(15, 7000)
        coefficients = np.empty((len(selected), 2), dtype=complex)
        for offset in range(0, len(selected), 128):
            bins = selected[offset:offset+128]
            exponent = np.exp((-2j*np.pi/n)*bins[:, None]*time[None, :])
            coefficients[offset:offset+len(bins)] = exponent@weighted
        frequency = selected*rate/n
        cells = 2*abs(coefficients)**2/(n*np.dot(window, window))
        actual = np.array([cells[(frequency >= lo)&(frequency < hi)].sum(axis=0) for lo,hi in bands])
        observation = next(x for x in observed['observations'] if x['id'] == ('F2_tailpipe' if key.startswith('F2') else 'runtime_full_recipe_idle'))
        expected = np.array(observation['per_tile_power'][0])
        error = float(np.linalg.norm(actual-expected)/np.linalg.norm(expected))
        assert error <= 1e-10
        literal.append(dict(id=observation['id'], bins=len(selected), relative_band_vector_error=error,
            all_selected_bins_direct_DFT=True))
    r['literal_DFT'] = literal
    folder = args.workspace/'references/analysis/full_recipe_drive_v1/verify1/full_pedals'
    trace = np.genfromtxt(folder/'pedal_trace.csv', delimiter=',', names=True)
    first, stop = observed['runtime']['frame_interval']
    chosen = trace[(trace['frame'] >= first)&(trace['frame'] < stop)]
    assert np.all((chosen['lifecycle'] == 4)&(chosen['operating'] == 0))
    assert np.max(chosen['resonant_support']) == np.max(chosen['coherent_low_support']) == 0
    for name in ('detail_stem', 'coherent_low_stem'):
        with sf.SoundFile(folder/(name+'.wav')) as stream:
            stream.seek(first); stem = stream.read(stop-first, always_2d=True)
        assert np.count_nonzero(stem) == 0
    assert np.array_equal(np.array(observed['runtime']['highest_main_carrier_range']),
        300*np.array([chosen['root_hz'].min(), chosen['root_hz'].max()]))
    earlier = args.workspace/'references/analysis/idle_material_v1/observe1/report.json'
    failed = load(earlier); assert failed['result'] == 'failed' and 'IndexError' in failed['error']
    # Earlier observations are reused, not silently discarded after parser fix.
    assert failed['observations'] == observed['observations'][:4]
    f2 = np.array(observed['observations'][0]['fraction_of_mean_band_power'])
    current = np.array(observed['observations'][-1]['fraction_of_mean_band_power'])
    r.update(result='all30_native_tiles_and2_literal_fullband_DFTs_verified',
        actual_tiles=sum(x['tiles'] for x in observed['observations']),
        current_idle_detail_and_low_exact_zero=True,
        above2200_fraction_F2=float(f2[4:,0].sum()), above2200_fraction_runtime=float(current[4:,0].sum()),
        F2_fractional_power_400_2200=float(f2[2:4,0].sum()), runtime_fractional_power_400_2200=float(current[2:4,0].sum()),
        parser_failure_and_exact_sources_retained=True, previous_partial_observations_exact=True,
        source_RPM_identified=False, physical_source_separation=False, new_model_permitted=False,
        next='Idle needs its own material-backed spectrum and mechanical texture. Preserve moving35 and complete the qualified common-phase extractor for an idle DNA, with independent fixed-Hz detail budget.',
        limits=['Cross-record level fractions compare recorded spectral shape only, not physical engine energy or exact EQ gains.',
            'This establishes missing coverage in the current full-recipe idle, not a synthesized improvement or full idle model.'])
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(args.out/'report.json', r)
print(json.dumps({k:r[k] for k in ('result','actual_tiles','above2200_fraction_F2','above2200_fraction_runtime')}, ensure_ascii=False), flush=True)
