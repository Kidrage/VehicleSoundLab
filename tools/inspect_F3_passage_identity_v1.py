"""Compare the two approved, visually selected F3 fifth-gear passages."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
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
report = dict(schema='vsl.F3-passage-identity/1', result='running', sources={},
    real_audio_read=False, model_exported=False, runtime_changed=False, timbre_accepted=False)
try:
    plan_path = repo/'research/F3_passage_identity_v1_plan.json'
    plan = load(plan_path)
    approved = load(repo/'research/approved_state_media_v1_plan.json')
    prior = args.workspace/'references/analysis/state_media_v1/F3_inspect1'
    inspection = load(prior/'report.json')
    assert inspection['identity'] == 'F3' and inspection['result'] == 'raw_recording_measured_and_coarse_video_prepared'
    assert sha(args.workspace/inspection['input_file']) == inspection['input_sha256']
    source = prior/inspection['decoded']['file']
    assert sha(source) == inspection['decoded']['sha256']
    paths = {Path(__file__), plan_path, repo/'research/approved_state_media_v1_plan.json',
        repo/'research/state_media_v1_visual_review.json', repo/'tools/drive_evidence_v1/sources.py',
        *sorted((repo/'tools/passage_identity_v1').glob('*.py'))}
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    report['controls'] = check(48000, plan['copy_evidence_gates'])
    with sf.SoundFile(source) as stream:
        rate = stream.samplerate
        assert rate == 48000 and stream.channels == 2 and stream.subtype == 'FLOAT'
        first, stop = [round(value*rate) for value in plan['template_audio_seconds']]
        stream.seek(first)
        template = stream.read(stop-first, dtype='float64', always_2d=True)
        margin = round(plan['maximum_integer_lag_seconds']*rate)
        second, second_stop = [round(value*rate) for value in plan['second_nominal_audio_seconds']]
        stream.seek(second-margin)
        search = stream.read(second_stop-second+2*margin, dtype='float64', always_2d=True)
    report['real_audio_read'] = True
    measured, arrays = match(template, search, rate, margin)
    assert measured['FFT_vs_direct_vs_scalar_maximum_error'] <= 1e-12
    positive = passes(measured, plan['copy_evidence_gates'])
    np.savez_compressed(args.out/'comparison.npz', template=template, search=search, **arrays)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 1, figsize=(10, 6), layout='constrained')
    axes[0].plot(arrays['lag_seconds'], arrays['candidate_NCC'])
    axes[0].axvline(measured['integer_lag_seconds'], color='k', linestyle='--', linewidth=.8)
    axes[0].set(xlabel='Second-passage integer lag (seconds)', ylabel='Paired stereo NCC',
                title='F3: 159..162s versus nominal190..193s; one fixed search range')
    values = [row['joint_NCC'] for row in measured['contiguous_blocks']]
    labels = ['Block '+str(index+1) for index in range(len(values))]
    values.extend(row['fixed_lag_joint_NCC'] for row in measured['fixed_lag_high_bands'])
    labels.extend(('3..6 kHz', '6..14 kHz'))
    axes[1].bar(labels, values)
    axes[1].set(ylabel='NCC at the one selected lag', ylim=(-1, 1), title='No per-block or per-band realignment')
    figure.savefig(args.out/'F3_passage_identity.png', dpi=150)
    plt.close(figure)
    report.update(result='strong_direct_shared_waveform_evidence' if positive else 'no_direct_integer_shift_copy_established',
        source_master=source.relative_to(args.workspace).as_posix(), source_master_sha256=sha(source),
        source_inspection_report_sha256=sha(prior/'report.json'),
        approval_plan_sha256=sha(repo/'research/approved_state_media_v1_plan.json'),
        plan=plan, measurement=measured, copy_evidence_gates_passed=positive,
        second_best_matched_audio_seconds=[second/rate+measured['integer_lag_seconds'],
                                          second_stop/rate+measured['integer_lag_seconds']],
        comparison_sha256=sha(args.out/'comparison.npz'), plot_sha256=sha(args.out/'F3_passage_identity.png'),
        independent_take_established=False, original_master_unchanged=(sha(source) == inspection['decoded']['sha256']),
        limitations=['A match supports shared waveform under this simple time/gain/DC model, not common physical source attribution',
            'A failed direct match does not prove independent takes or rule out transformed/reedited audio',
            'No fractional-delay/time-warp/remix search and no listening-quality or calibrated RPM/load conclusion',
            'Original phase extractor qualification remains failed; no new engine DNA or runtime state map'])
    print(json.dumps(dict(result=report['result'], measurement=measured)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
