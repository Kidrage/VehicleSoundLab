"""Check whether nearby A contexts provide independent acoustic references."""
import argparse
from pathlib import Path
import shutil
import itertools

import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    out = p.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_audit.py')
    root = Path('E:/VehicleSoundLab/references/analysis/event_full_envelope_v1/A-contexts1')
    contexts = {path.name: sf.read(path/'original.wav', dtype='float64', always_2d=True)[0]
                for path in root.iterdir() if path.is_dir() and (path/'original.wav').is_file()}
    results = []
    for left, right in itertools.combinations(contexts, 2):
        x = contexts[left][48000:96000]
        y = contexts[right][48000-1920:96000+1920]
        correlation = signal.correlate(y[:, 0], x[:, 0], mode='valid', method='fft')
        start = int(np.argmax(abs(correlation)))
        match = y[start:start+len(x)]
        gain = float(np.sum(x*match)/np.sum(match*match))
        residual = x-gain*match
        coefficient = float(np.sum(x*match)/np.sqrt(np.sum(x*x)*np.sum(match*match)))
        results.append(dict(left=left, right=right, shift_frames=start-1920,
            stereo_correlation=coefficient, least_squares_gain=gain,
            relative_residual_rms=float(np.sqrt(np.sum(residual*residual)/np.sum(x*x))),
            equal_float_samples=bool(np.array_equal(x, match))))
    save(out/'report.json', dict(result='passed', analysis_window_seconds=[1., 2.],
        alignment_search_frames=[-1920, 1920], pairs=results,
        input_sha256={name: sha(root/name/'original.wav') for name in contexts},
        limitation='Correlation can reveal reused acoustic content; it cannot establish why a video was edited or classify an event.'))
    print(results, flush=True)


if __name__ == '__main__':
    main()
