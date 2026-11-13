"""Subsequent phase-dependent global bound; original regression gate unchanged."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']:
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
from research_archive_v1 import load, save, sha
from idle_phase_difference_v1.positivity import controls, certify

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, observations=[])
try:
    for name in ['tools/bound_idle_phase_difference_v1.py', 'tools/idle_phase_difference_v1/positivity.py',
                 'tools/research_archive_v1.py', 'research/idle_phase_difference_v1_bound_plan.json']:
        path = repo/name; dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest); r['sources'][name] = sha(path)
    r['known'] = controls()
    print(dict(stage='known_global_bounds', result='passed'), flush=True)
    observed = load(a.input/'report.json')
    assert observed['result'] == 'all_nested_phase_difference_observations_complete'
    for row in observed['observations']:
        result = certify(row['models']['expanded']['coefficients'])
        r['observations'].append(dict(group=row['group'], certificate=result))
        print(dict(group=row['group'], certificate=result), flush=True)
    r.update(result='dependent_phase_bounds_complete_no_sound_promotion',
             input_report_sha256=sha(a.input/'report.json'),
             original_gate_unchanged=observed['future_synthesis_prerequisite'],
             audio_or_runtime_profile_exported=False, runtime_changed=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc)); raise
finally:
    save(a.out/'report.json', r)
