"""Replay source slices and all identity controls; independently check selected-lag dots."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from passage_identity_v1.match import match, passes
from passage_identity_v1.checks import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.F3-passage-identity-audit/1', result='running', sources={},
    real_audio_read=True, model_exported=False, runtime_changed=False,
    independent_take_established=False, timbre_accepted=False)
try:
    candidate = load(args.candidate/'report.json')
    assert candidate['result'] == 'no_direct_integer_shift_copy_established'
    paths = {Path(__file__)}
    for relative, digest in candidate['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    source = args.workspace/candidate['source_master']
    assert sha(source) == candidate['source_master_sha256']
    plan = candidate['plan']
    assert check(48000, plan['copy_evidence_gates']) == candidate['controls']
    rate = 48000
    margin = round(plan['maximum_integer_lag_seconds']*rate)
    frames = round((plan['template_audio_seconds'][1]-plan['template_audio_seconds'][0])*rate)
    with sf.SoundFile(source) as stream:
        stream.seek(round(plan['template_audio_seconds'][0]*rate))
        first = stream.read(frames, dtype='float64', always_2d=True)
        stream.seek(round(plan['second_nominal_audio_seconds'][0]*rate)-margin)
        search = stream.read(frames+2*margin, dtype='float64', always_2d=True)
    assert sha(args.candidate/'comparison.npz') == candidate['comparison_sha256']
    saved = np.load(args.candidate/'comparison.npz')
    assert np.array_equal(first, saved['template']) and np.array_equal(search, saved['search'])
    measured, arrays = match(first, search, rate, margin)
    assert measured == candidate['measurement']
    assert all(np.array_equal(value, saved[key]) for key, value in arrays.items())
    assert passes(measured, plan['copy_evidence_gates']) == candidate['copy_evidence_gates_passed'] == False
    dots = []
    for index in sorted(set((0, margin, len(arrays['candidate_NCC'])-1, measured['selected_search_sample']))):
        second = search[index:index+frames]
        first_centered = first-np.mean(first, axis=0)
        second_centered = second-np.mean(second, axis=0)
        numerator = sum(float(first_centered[:, channel]@second_centered[:, channel]) for channel in range(2))
        denominator = np.sqrt(sum(float(first_centered[:, channel]@first_centered[:, channel]) for channel in range(2))*
            sum(float(second_centered[:, channel]@second_centered[:, channel]) for channel in range(2)))
        actual = float(numerator/denominator)
        error = abs(actual-float(arrays['candidate_NCC'][index]))
        assert error <= 1e-12
        dots.append(dict(search_sample=index, direct_NCC=actual, FFT_difference=error))
    assert measured['selected_search_sample'] == int(np.argmax(abs(saved['candidate_NCC'])))
    report.update(result='F3_source_slices_controls_and_fixed_lag_identity_measurements_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), all_slices_and_measurements_exact=True,
        independent_lag_dot_checks=dots, source_master_unchanged=True,
        limitations=candidate['limitations'])
    print(json.dumps(dict(result=report['result'], direct_checks=dots)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
