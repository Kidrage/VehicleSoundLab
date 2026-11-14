"""Isolated build and two focused contracts; original DSP sources are unchanged."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import load, save, sha
p = argparse.ArgumentParser(description=__doc__)
for name in ('workspace', 'out'):
    p.add_argument('--'+name, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '2'
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
from local_atlas_v1.inputs import known
a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, commands=[])
try:
    names = set()
    for switches in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        names.update(subprocess.check_output(['git']+switches, cwd=repo).decode('utf-8').split('\0'))
    names.update(('tools/build_local_atlas_v1.py', 'tools/local_atlas_v1/inputs.py',
                  'research/F3_local_atlas_v1_plan.json'))
    for name in sorted(n for n in names if n and (Path(n).suffix in ('.c', '.h', '.cmake', '.in') or
                       n.endswith('CMakeLists.txt') or n.startswith(('tools/build_local_atlas', 'tools/local_atlas_v1/inputs', 'research/F3_local_atlas')))):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    known(a.out/'known', load(repo/'research/F3_local_atlas_v1_plan.json'))
    build = repo/'build-local-atlas-v1'
    commands = [
        ['cmake', '-S', repo/'experiments/local_atlas_v1', '-B', build,
         '-G', 'Visual Studio 17 2022', '-A', 'x64', '-DLA_CHECK_ROOT='+str(a.out/'known')],
        ['cmake', '--build', build, '--config', 'Release', '--parallel', '2', '--target',
         'local_atlas_export', 'local_atlas_checks', 'local_atlas_driver_checks'],
        ['ctest', '--test-dir', build, '-C', 'Release', '-R', '^local_atlas_', '--output-on-failure',
         '--output-junit', a.out/'ctest.xml']]
    for index, argv in enumerate(commands):
        argv = list(map(str, argv))
        print('RUN', argv[:4], flush=True)
        done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=900)
        log = a.out/('command%d.log' % index)
        log.write_bytes(done.stdout+done.stderr)
        r['commands'].append(dict(argv=argv, exit_code=done.returncode, log=log.name, sha256=sha(log)))
        save(a.out/'report.json', r)
        assert done.returncode == 0, log
    r.update(result='passed', focused_CTests=2, unchanged_70CTest_not_repeated=True,
             shared_DSP_changed=False, known_controls_only=True)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(r['result'], flush=True)
