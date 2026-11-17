"""Reproducible original-context diagnostics before event parameter fitting."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('job', type=Path)
    p.add_argument('--context', nargs=2, type=float, required=True)
    p.add_argument('--after', nargs=2, type=float, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, 'E:/VehicleSoundLab/tools/python_deps')
    from event_authoring.context import probe, plot
    from event_authoring.band_scope import normalize
    from event_authoring.audio import sha
    job = json.loads(a.job.read_text(encoding='utf-8-sig'))
    source = Path(job['source'])
    if not source.is_absolute():source = (a.job.parent/source).resolve()
    backgrounds = dict(before=job['background_seconds'], after=a.after)
    intervals = [job['seconds'], *backgrounds.values()]
    if not all(a.context[0] <= x[0] < x[1] <= a.context[1] for x in intervals):
        raise ValueError('Context must contain event and both backgrounds')
    scope = normalize(job.get('analysis_scope'))
    report, arrays = probe(source, job['seconds'], backgrounds, scope)
    a.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(a.job, a.output/'input.job.json')
    exact = a.output/'exact_sources';exact.mkdir()
    for path in [Path(__file__), *sorted(Path(__file__).with_name('event_authoring').glob('*.py'))]:
        shutil.copy2(path, exact/path.name)
    plot(source, a.context, job['seconds'], backgrounds, scope, arrays, a.output/'context.png')
    report.update(source_job=job, context_seconds=a.context,
        source_files={p.name:sha(p) for p in exact.glob('*.py')})
    (a.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(dict(output=str(a.output), sample_peak_seconds=report['sample_peak_seconds'],
        contrasts=[{k:r[k] for k in ('name','full_contrast_db','scoped_contrast_db')} for r in report['backgrounds']]), ensure_ascii=False))


if __name__ == '__main__':main()
