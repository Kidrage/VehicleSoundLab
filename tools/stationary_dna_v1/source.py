"""Check and split an existing stationary coordinate without refitting it."""
import json
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from phase_clock_v1.projection import independent_agreement
from startup_catch_v1.clock import diagnostics
from .measure import moments, difference


def inspect(directory, case, plan):
    original = json.loads((directory/'report.json').read_text(encoding='utf-8'))
    assert original['local_diagnostic_gate'] is False
    reference = case['primary_reference']
    evidence = original['references'][str(reference)]
    assert evidence['status'] == 'observed'
    path = directory/f'reference{reference}_normalized.wav'
    audio, rate = sf.read(path, always_2d=True)
    assert rate == 48000 and audio.shape[1] == 2 and np.isfinite(audio).all()
    coordinates = directory/f'reference{reference}_coordinates.npz'
    with np.load(coordinates, allow_pickle=False) as z:
        where = z['source_seconds']
    assert len(where) == len(audio) and np.all(np.diff(where)>0)
    base = float(np.median(1/(1024*np.diff(where))))
    # Split at an integral cycle so neither half's four-cycle observation
    # contains a sample from the other half. No row-wise random split.
    split = len(audio)//2048*1024
    train, heldout = audio[:split], audio[split:]
    halves = [independent_agreement(diagnostics(x, reference)) for x in (train, heldout)]
    delta = difference(moments(train,base,plan['harmonics'],plan['bands_hz']),
                       moments(heldout,base,plan['harmonics'],plan['bands_hz']))
    power_error = float(abs(np.asarray(delta['power_difference_db_LR'])).max())
    correlation_error = float(max(delta['complex_correlation_difference']))
    counts = [len(x)//4096 for x in (train,heldout)]
    rules = plan['rules']
    passed = bool(all(x['passed'] for x in halves) and
        min(counts)>=rules['minimum_four_cycle_windows_per_half'] and
        power_error<=rules['maximum_heldout_band_power_difference_db'] and
        correlation_error<=rules['maximum_heldout_complex_correlation_difference'])
    info = dict(case=case, acoustic_root_hz=base, reference=reference,
        source_normalized_sha256=sha(path), source_coordinates_sha256=sha(coordinates),
        original_report_sha256=sha(directory/'report.json'), original_local_gate=False,
        original_generic_gate='not_passed_unchanged', split_normalized_sample=split,
        train_source_seconds=[float(where[0]),float(where[split-1])],
        heldout_source_seconds=[float(where[split]),float(where[-1])],
        nonoverlapping_four_cycle_windows=counts, independent_halves=halves,
        heldout_difference=delta,maximum_heldout_power_difference_db=power_error,
        maximum_heldout_correlation_difference=correlation_error,stationary_scope_passed=passed,
        scope='Conditional acoustic stationary extraction only; no physical RPM/load/temperature claim')
    return train,heldout,info
