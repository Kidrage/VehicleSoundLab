"""Known-first half-angle lift controls; no material/model access or audio UI."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import numpy as np
    from circular_phase_lift_v1.fixtures import run
    repo = Path(__file__).resolve().parents[1]
    plan = load(repo/'research/circular_phase_lift_v1_plan.json')
    args.out.mkdir(parents=True, exist_ok=False)
    names = ['tools/run_circular_phase_lift_known_v1.py', 'tools/circular_phase_lift_v1/lift.py',
             'tools/circular_phase_lift_v1/fixtures.py', 'research/circular_phase_lift_v1_plan.json']
    for name in names:
        path = args.out/'exact_sources'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, path)
    rows, paths = run()
    assert set(rows) == set(plan['known_controls'])
    gate = plan['known_gates']
    for label in ('positive_branch', 'negative_branch'):
        assert rows[label]['phase_error'] < gate['phase_or_wave_absolute']
        assert rows[label]['wave_error'] < gate['phase_or_wave_absolute']
        assert rows[label]['off_analytic_bins_power'] < gate['analytic_spectral_leak_power']
        assert rows[label]['branch_increments'] > 0
    assert rows['no_crossing_exact']['bit_exact'] and rows['no_crossing_exact']['zero_winding']
    assert rows['gauge_compensation']['coefficient_error'] < gate['phase_or_wave_absolute']
    assert rows['gauge_compensation']['wave_error'] < gate['phase_or_wave_absolute']
    assert rows['held_common_changes_wave']['wave_difference_RMS'] > .1
    assert rows['held_common_changes_wave']['circular_error'] < gate['phase_or_wave_absolute']
    assert max(rows['instantaneous_stereo_invariants'].values()) < gate['phase_or_wave_absolute']
    assert rows['fast_motion_ambiguity']['aliased_phase_error'] < gate['phase_or_wave_absolute']
    assert rows['fast_motion_ambiguity']['circular_indistinguishability'] < gate['phase_or_wave_absolute']
    assert rows['fast_motion_ambiguity']['lift_differs_from_fast']
    assert rows['fast_motion_ambiguity']['half_turn_steps_flagged'] == 3
    files = {}
    for label, arrays in paths.items():
        path = args.out/(label+'.npz')
        np.savez_compressed(path, **arrays)
        files[path.name] = sha(path)
    report = dict(result='circular_phase_lift_known_ready', cases=rows,
                  sources={name:sha(repo/name) for name in names}, files=files,
                  recordings_or_models_read=False, new_runtime_or_listening=False,
                  equivalent_waveform_fix=False)
    save(args.out/'report.json', report)
    print(report['result'])
    print(rows)


if __name__ == '__main__':
    main()
