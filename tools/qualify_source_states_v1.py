"""Apply the existing local coordinate estimator to fixed source observations."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--observed', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--plan', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from local_voice_v1.qualification import qualify

args.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(Path(__file__), args.out / 'executed_qualify.py')
report = dict(schema='vsl.source-stationary-coordinate/1', result='running', cases={}, sources={})
try:
    plan_path = args.plan.resolve()
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    previous = json.loads((args.observed / 'report.json').read_text(encoding='utf-8'))
    assert previous['schema'] == 'vsl.source-state-observation/1'
    assert previous['result'] == 'observed_not_fitted'
    assert previous['input']['source'] == plan['source']
    report['observation_report_sha256'] = sha(args.observed / 'report.json')
    for name, digest in previous['sources'].items():
        assert sha(args.observed / 'exact_sources' / name) == digest
    sources = [Path(__file__), plan_path, repo / 'tools/drive_evidence_v1/sources.py']
    for package in ('local_voice_v1', 'state_colour_v2', 'state_dna_v1',
                    'phase_clock_v1', 'exterior_clock_v1', 'sound_dna'):
        sources += list((repo / 'tools' / package).glob('*.py'))
    for source in sources:
        relative = source.relative_to(repo)
        target = args.out / 'exact_sources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    master = args.workspace / previous['input']['master']
    assert sha(master) == previous['input']['master_sha256']
    report['master_sha256'] = sha(master)
    for case in plan['cases']:
        item = previous['segments'][case['observation']]
        measurement = item['observations'][str(case['window_ms'])]
        observed_path = args.observed / case['observation'] / f"observations_{case['window_ms']}ms.npz"
        assert sha(observed_path) == measurement['observations_sha256']
        with np.load(observed_path, allow_pickle=False) as archive:
            observed = {key: archive[key] for key in archive.files}
        lo, hi = item['case']['seconds']
        assert lo <= case['seconds'][0] < case['seconds'][1] <= hi
        with sf.SoundFile(master) as stream:
            assert (stream.samplerate, stream.channels, stream.subtype) == (48000, 2, 'FLOAT')
            first, stop = [round(seconds * 48000) for seconds in (lo, hi)]
            stream.seek(first)
            audio = stream.read(stop-first, dtype='float64', always_2d=True)
        out = args.out / case['id']
        out.mkdir()
        local_plan = dict(plan, primary_reference=case['primary_reference'],
                          comparison_references=case['comparison_references'])
        result = qualify(audio, lo, observed, case, local_plan, out)
        result['input_observation_sha256'] = measurement['observations_sha256']
        (out / 'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        report['cases'][case['id']] = result
        print(json.dumps(dict(case=case['id'], local_gate=result['local_diagnostic_gate'],
            references={key: value['status'] for key, value in result['references'].items()},
            comparisons=result['comparisons'])), flush=True)
    report.update(result='local_diagnostics_only', plan=plan, limits=plan['limits'],
                  model_exported=False, runtime_modified=False)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out / 'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
