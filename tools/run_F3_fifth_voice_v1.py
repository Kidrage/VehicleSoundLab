"""Two declared F3 local observations; no source-dependent rescue or C changes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'out', 'dna-probe'):
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
from local_voice_batch_v1.batch import controls, fit_case
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, cases=[])
try:
    names = ['tools/run_F3_fifth_voice_v1.py', 'research/F3_fifth_voice_v1_plan.json',
             'research/F3_display_rpm_v1_annotations.json', 'tools/research_archive_v1.py',
             'tools/drive_evidence_v1/sources.py', 'tools/drive_evidence_v1/family.py',
             'tools/shift_evidence_v1/spectrum.py', 'tools/B_shift_voice_v1/selection.py',
             'tools/decel_source_v1/aperture.py', 'tools/decel_source_v1/checks.py',
             'tools/exterior_clock_v1/warp.py', 'tools/local_voice_batch_v1/batch.py']
    names += [v.relative_to(repo).as_posix() for v in (repo / 'tools/sound_dna').glob('*.py')]
    for n in sorted(set(names)):
        dest = a.out / 'exact_sources' / n
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / n, dest)
        r['sources'][n] = sha(repo / n)
    plan = load(repo / 'research/F3_fifth_voice_v1_plan.json')
    assert plan['schema'] == 'vsl.local-voice-batch/1'
    protocol = subprocess.check_output([str(a.dna_probe), '--describe'], cwd=repo).decode('utf-8').strip()
    assert protocol == 'vsl.sound-dna-raw-export/1'
    r['export_protocol'] = protocol
    r['known_before_source'] = controls(plan)
    save(a.out / 'report.json', r)
    catalog = a.workspace / 'references/segments_v1.json'
    assert sha(catalog) == sha(repo / 'references/segments_v1.json')
    r['inputs'][str(catalog)] = sha(catalog)
    source = load(catalog)['sources']['F3']
    for key in ('raw', 'master'):
        path = a.workspace / source[key]
        assert sha(path) == source[key + '_sha256']
        r['inputs'][str(path)] = sha(path)
    r['inputs'][str(a.dna_probe)] = sha(a.dna_probe)
    for case in plan['cases']:
        row = fit_case(a.workspace, case, plan, a.out / case['name'], a.dna_probe, repo)
        r['cases'].append(row)
        save(a.out / case['name'] / 'result.json', row)
        save(a.out / 'report.json', r)
        print(dict(name=case['name'], qualified=row['qualified'], stage=row['stage'],
                   root_hz=row.get('extraction', {}).get('root_hz'),
                   heldout=row.get('extraction', {}).get('heldout_coherence')), flush=True)
    r.update(result='fixed_F3_fifth_local_cases_checked', qualified=sum(v['qualified'] for v in r['cases']),
             excluded=sum(not v['qualified'] for v in r['cases']), runtime_changed=False,
             new_timbre_accepted=False, physical_RPM_or_load=False, generic_phase_qualified=False,
             room=False, PCM_timeline=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
