"""Freeze exterior startup selections and create jobs before any fitting."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    out = p.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    selection = load(repo/'research/A_exterior_startup_v1_selection.json')
    source = Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    assert sha(source) == selection['source_sha256']
    shutil.copy2(__file__, out/'executed_preparation.py')
    shutil.copy2(repo/'research/A_exterior_startup_v1_selection.json', out/'selection.json')
    intervals = dict(background=selection['background_seconds'], early=selection['early_seconds'],
                     later=selection['later_seconds'], context=selection['full_reference_seconds'])
    powers, provenance = {}, {}
    with sf.SoundFile(source) as stream:
        assert stream.samplerate == 48000 and stream.channels == 2
        for name, interval in intervals.items():
            first, last = [round(t*48000) for t in interval]
            stream.seek(first)
            x = stream.read(last-first, dtype='float64', always_2d=True)
            assert len(x) == last-first and np.isfinite(x).all()
            powers[name] = sum(float(x[:, c] @ x[:, c]) for c in range(2))/(2*len(x))
            sf.write(out/(name+'-original.wav'), x, 48000, subtype='FLOAT')
            sf.write(out/(name+'-monitor.wav'), .25*x, 48000, subtype='FLOAT')
            provenance[name] = dict(frames=[first, last], power=powers[name],
                                    original_sha256=sha(out/(name+'-original.wav')))
    jobs = {}
    for kind, name, gated in [('crank', 'early', True), ('catch', 'later', False)]:
        job = dict(schema='vsl.event-authoring-job/8', kind=kind,
            name='A 车外启动 · '+('早期纹理候选' if gated else '接火阶段声学候选'),
            source=str(source), seconds=intervals[name], background_seconds=intervals['background'],
            analysis_scope=dict(mode='full'), response_fit='source-response-v1',
            envelope_fit='band-contour-v4', gated=gated, physical_identity_confirmed=False,
            context='Approved A exterior rear source, fixed before fit after whole-action context review. '+
                ('Early acoustic interval; not physically separated starter or measured crank RPM. ' if gated else
                 'Later acoustic interval includes ongoing engine; not isolated additive catch and may double-count DNA. ')+
                'Original whole-action context47.0..51.0s retained. No normalization, room model, PCM playback or automatic physical timing inference.')
        save(out/(kind+'.job.json'), job)
        jobs[kind] = dict(path=str(out/(kind+'.job.json')),
            contrast_db=float(10*np.log10(powers[name]/powers['background'])))
    runtime = {path.relative_to(repo).as_posix(): sha(path) for group in ('src', 'modules', 'voices')
               for path in (repo/group).rglob('*') if path.is_file() and (path.suffix in ('.c', '.h') or group == 'voices')}
    assert len(runtime) == 459
    save(out/'runtime.json', runtime)
    save(out/'report.json', dict(result='passed', source_sha256=sha(source), jobs=jobs,
        selections=provenance, physical_source_separated=False, physical_RPM_identified=False,
        original_reference_preserved=True, prior_to_any_source_fit=True))
    print(jobs, flush=True)


if __name__ == '__main__':
    main()
