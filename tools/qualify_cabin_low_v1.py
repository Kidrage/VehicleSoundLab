"""Run one predeclared existing local qualification on each new B context."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--observed', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from local_voice_v1.qualification import qualify

a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.cabin-low-qualification/1', result='running', cases={}, sources={})
try:
    plan_path = repo/'research/cabin_low_v1_qualification_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    inputs = [Path(__file__), plan_path, repo/'tools/local_voice_v1/qualification.py',
        repo/'tools/drive_evidence_v1/sources.py', repo/'tools/state_colour_v2/clock.py',
        repo/'tools/state_dna_v1/compare.py', repo/'tools/phase_clock_v1/projection.py',
        repo/'tools/exterior_clock_v1/warp.py', repo/'tools/sound_dna/windowed.py']
    for file in inputs:
        name = file.relative_to(repo); target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(file, target)
        r['sources'][name.as_posix()] = sha(file)
    previous = json.loads((a.observed/'report.json').read_text(encoding='utf-8'))
    assert previous['result'] == 'observed_not_fitted'
    r['observation_report_sha256'] = sha(a.observed/'report.json')
    for name, digest in previous['sources'].items():
        assert sha(a.observed/'exact_sources'/name) == digest
    master = a.workspace/previous['input']['master']
    assert sha(master) == previous['input']['master_sha256']
    r['master_sha256'] = sha(master)
    for case in plan['cases']:
        item = previous['segments'][case['observation']]
        observed_path = a.observed/case['observation']/'observations.npz'
        assert sha(observed_path) == item['observation_sha256']
        with np.load(observed_path, allow_pickle=False) as z:
            observed = {key:z[key] for key in z.files}
        lo, hi = item['provenance']['seconds']
        with sf.SoundFile(master) as stream:
            assert stream.samplerate == 48000 and stream.channels == 2 and stream.subtype == 'FLOAT'
            stream.seek(round(lo*48000))
            audio = stream.read(round((hi-lo)*48000), dtype='float64', always_2d=True)
        out = a.out/case['id']; out.mkdir()
        result = qualify(audio, lo, observed, case, plan, out)
        result['input_observation_sha256'] = item['observation_sha256']
        (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        r['cases'][case['id']] = result
        print(json.dumps(dict(case=case['id'], local_gate=result['local_diagnostic_gate'],
            references={k:v['status'] for k,v in result['references'].items()},
            comparisons=result['comparisons']),ensure_ascii=False),flush=True)
    r.update(result='local_diagnostics_only', plan=plan, limits=plan['limits'],
        model_exported=False, runtime_modified=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
