"""Diagnose fixed-crop contour conditioning without changing authoring defaults."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.contour_all_bands import observations
from event_authoring.contour_joint import fit_shape, shape_errors
from event_authoring.measure import observe
from event_authoring.response_basis import calibrate_unit
from research_archive_v1 import load, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_probe.py')
    root = Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    x, _ = sf.read(root/'selection1/later-original.wav', always_2d=True)
    background, _ = sf.read(root/'selection1/background-original.wav', always_2d=True)
    profile = load(root/'catch1/refused-fit.json')
    _, arrays = observe(x, background)
    _, target, rows = observations(x, background)
    duration = len(x)/48000
    indices = [k for k, row in enumerate(rows) if row['selected']]
    entry = shape_errors(profile, target, duration, indices)
    fitted, shape = fit_shape(profile, target, duration, rows, band_offset=0,
                             weights=1/np.maximum(entry, .05))
    save(out/'shaped-profile.json', fitted)
    print('shape fitted', [c['gain'] for c in fitted['contours']], flush=True)
    report = dict(entry_shape_rmse=entry, shape=shape, candidates={})
    for name, normalized in [('original', False), ('unit_peak', True)]:
        p = deepcopy(fitted)
        if normalized:
            for contour in p['contours']:
                scale = max(contour['gain'])
                if scale > 1e-12:
                    contour['gain'] = [g/scale for g in contour['gain']]
        p, response = calibrate_unit(p, arrays, duration)
        save(out/(name+'.json'), p)
        report['candidates'][name] = dict(response=response,
            shape_rmse=shape_errors(p, target, duration, indices),
            contour_peaks=[max(c['gain']) for c in p['contours']])
        print(name, response['qualified'], report['candidates'][name]['shape_rmse'], flush=True)
    save(out/'report.json', report)


if __name__ == '__main__':
    main()
