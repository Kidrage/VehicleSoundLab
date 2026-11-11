"""Exact accepted64OSC plus separately observed high frequencies and C pitch.

The historical mixed-perspective base is preserved for identity. New high
observations come ONLY from the catalogue-approved exterior moving interval.
"""
from runtime_review import ROOT, sha
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from reference_segments import read_segment
from reference_osc_v2.tracked_fit import fit, export, Settings
from reference_osc_v1.observations import compare

OUT = ROOT/'references/analysis/reference_osc_v2'
PROBE = ROOT/'build-reference-osc-v2/Release/tracked_osc_probe.exe'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def render(model, ids, name, pitch, high):
    path = OUT/f'{name}_float.wav'
    done = subprocess.run([str(PROBE), str(model), str(ids), str(path), str(pitch), str(high)],
        check=True, capture_output=True, text=True, timeout=120)
    audio, rate = sf.read(path, always_2d=True)
    return audio, dict(file=path.name, sha256=sha(path), pitch=pitch, high=high, log=done.stdout.strip())


def main():
    OUT.mkdir(exist_ok=False)
    previous = json.loads((ROOT/'references/analysis/reference_osc_v1/results.json').read_text(encoding='utf-8'))
    baseline = json.loads((ROOT/'research/timbre_baseline_20261110.json').read_text(encoding='utf-8'))
    accepted = ROOT/baseline['accepted_reference']['file']
    assert sha(accepted) == baseline['accepted_reference']['sha256']
    source = ROOT/'references/clean/A_tailpipe_road_pull.wav'
    x, rate = sf.read(source, always_2d=True)
    # Explicit archival mono identity: no new stereo calibration from this clip.
    mono = x.mean(axis=1)
    base, base_segments, base_stats, next_id = fit(mono, rate, legacy=True)
    v1, v1rate = sf.read(ROOT/'references/analysis/reference_osc_v1/archive64_c_float.wav', always_2d=True)
    assert v1rate == rate and abs(base-v1).max() < 1e-7
    print('Accepted64 base tracking recovered.', flush=True)

    # Only permitted exterior source for new HF measurements. Preserve master.
    exterior, sr, provenance = read_segment('A_exterior_moving', 'exterior_dynamic_observation')
    assert sr == rate
    # Measure waveform alignment, independently of any video/RPM claim.
    legacy_start = round((316-313.5)*rate)
    margin = rate//5
    a = x[legacy_start+margin:-margin, 0]
    cross = signal.correlate(a, exterior[:, 0], method='fft')
    lags = signal.correlation_lags(len(a), len(exterior))
    lag = int(lags[np.argmax(cross)])
    offset = legacy_start+margin+lag
    assert abs(offset-legacy_start) <= round(.02*rate)
    # Reproduce the documented legacy fixed0.5/28Hz transfer for comparison.
    # The master and provenance are kept unchanged; mono is explicit for this
    # accepted mono model, not a replacement of the L/R analysis master.
    compatibility = signal.sosfilt(signal.butter(2, 28, btype='highpass', fs=rate, output='sos'),
                                   exterior*.5, axis=0).mean(axis=1)
    length = min(len(compatibility), len(mono)-offset)
    valid = slice(margin, length-margin)
    archival = mono[offset:offset+length]
    correlation = float(np.corrcoef(archival[valid], compatibility[:length][valid])[0, 1])
    assert correlation > .999, correlation
    reference = np.zeros_like(mono)
    reference[offset:offset+length] = compatibility[:length]
    residual = np.zeros_like(mono)
    residual[offset:offset+length] = reference[offset:offset+length]-base[offset:offset+length, 0]
    first, last = offset+1024, offset+length-1024
    groups, high_total, high_stats = [], np.zeros_like(base), {}
    for name, lower, upper, budget in [('presence', 3000, 8000, 16), ('upper', 8000, 14000, 24)]:
        value, segments, stats, next_id = fit(residual, rate, count=budget, group=1, id_start=next_id,
            settings=Settings(window=2048, lower_hz=lower, upper_hz=upper))
        # Full detector windows and interpolation intervals must stay inside
        # the catalogue-approved exterior source, including the right endpoint.
        segments = {start:rows for start, rows in segments.items() if start >= first and start+256 <= last}
        mask = np.zeros(len(value), dtype=bool)
        for start in segments:
            mask[start:start+256] = True
        value[~mask] = 0
        groups.append(segments)
        high_total += value
        high_stats[name] = dict(**stats, detector_hz=[lower, upper], support_budget=budget)
        print(name, 'high tracks fitted.', flush=True)
    model, ids = OUT/'accepted64_high.model', OUT/'accepted64_high.ids'
    representation = export(model, ids, rate, len(base), base_segments, *groups)
    c_base, transfer_base = render(model, ids, 'base', 1, 0)
    assert np.array_equal(c_base, v1), 'New unity-pitch renderer must reproduce V1 exactly'

    # Original audition gain recovered independently from its recorded PCM.
    # Use V1's original-gain recovery as a gain estimate only, then verify all
    # decoded samples against accepted original, including the original ramps.
    original, original_rate = sf.read(accepted)
    assert original_rate == rate
    valid_gain = slice(rate//5, -rate//5)
    gain = float(np.dot(original[valid_gain], c_base[valid_gain, 0])/np.dot(c_base[valid_gain, 0], c_base[valid_gain, 0]))
    def audition(name, value):
        y = value[:, 0]*gain
        y[:512] *= np.linspace(0, 1, 512)
        y[-512:] *= np.linspace(1, 0, 512)
        assert abs(y).max() < .95, 'Preserve base gain; never apply hidden limiting'
        path = OUT/f'{name}_audition.wav'
        sf.write(path, y, rate, subtype='PCM_24')
        return dict(file=path.name, sha256=sha(path), peak=float(abs(y).max()))
    auditions = {'base':audition('base', c_base)}
    decoded, _ = sf.read(OUT/auditions['base']['file'])
    original_error = float(abs(decoded-original).max())
    assert original_error <= 2/8388608
    transfers, comparisons = {'base':transfer_base}, {}
    for amount in [.25, .5]:
        name = 'high'+str(round(amount*100))
        value, transfer = render(model, ids, name, 1, amount)
        error = float(abs(value-(base+amount*high_total)).max())
        assert error < 1e-7
        auditions[name] = audition(name, value)
        transfers[name] = dict(**transfer, max_float_error=error)
        comparisons[name] = compare(np.column_stack([archival, archival]), value[offset:offset+length], rate)
    for name, ratio in [('pitch90', .9), ('pitch110', 1.1)]:
        value, transfer = render(model, ids, name, ratio, 0)
        assert len(value) == len(base)
        auditions[name] = audition(name, value)
        transfers[name] = transfer
    # Expose the *same* 3.5s approved exterior scope as a baseline metric.
    comparisons['base'] = compare(np.column_stack([archival, archival]), base[offset:offset+length], rate)
    result = dict(schema='vsl.reference-osc-review/2', accepted_baseline=baseline,
        native_release_changed=False, base_stats=base_stats, high_stats=high_stats,
        representation=representation, probe_sha256=sha(PROBE),
        model=dict(file=model.name, sha256=sha(model)), ids=dict(file=ids.name, sha256=sha(ids)),
        original_max_pcm24_error=original_error, unity_c_exact_v1=True,
        provenance=provenance,
        alignment=dict(legacy_sample_offset=offset, legacy_expected_offset=legacy_start,
            measured_difference_samples=offset-legacy_start,
            correlation_after_documented_transfer=correlation,
            compatibility_processing='Fixed0.5, causal28Hz Butterworth HP, explicit A L/R mean for accepted mono model. Originals unchanged.',
            caution='Waveform-domain alignment of independently decoded audio derivatives only. Not A/V or ECU timing.'),
        high_active_samples=[min(min(g) for g in groups), max(max(g)+256 for g in groups)],
        gain=gain, gain_db=float(20*np.log10(gain)),
        audition_processing='Same recovered original64 gain and512-sample endpoint ramps for every option; no per-version normalization, EQ of base, compression or limiting.',
        auditions=auditions, transfers=transfers, exterior_comparisons=comparisons,
        limits=['Accepted original64 timbre only; added high and transposition not yet subjectively accepted.',
            'Base is a historical mixed-perspective mono reconstruction, not a measured RPM/load voice.',
            'Added high uses only the catalogue-approved exterior interval and is zero in earlier cabin content.',
            'Relative pitch control changes oscillator frequencies while keeping the six-second trajectory duration. It does not produce arbitrary sustained engine states.',
            'Residual includes noise, microphone/space and modelling errors. Fitted high OSC is not an isolated physical source.',
            'Instantaneous polynomial frequency guard is not a proof of arbitrary AM/FM alias absence.'])
    assert sha(accepted) == baseline['accepted_reference']['sha256']
    for name, digest in previous['preserved_before'].items():
        assert sha(ROOT/name) == digest
    dump(OUT/'results.json', result)
    print('Accepted base preserved; C pitch/high renders and provenance checks passed.', flush=True)


if __name__ == '__main__':
    main()
