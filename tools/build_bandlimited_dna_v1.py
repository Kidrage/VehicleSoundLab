"""Capture consumed source bytes and build the opt-in path in an isolated tree."""
import argparse
from pathlib import Path
import shutil
import subprocess
import time
from research_archive_v1 import save, sha

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--phase', choices=['focused', 'all'], required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
build = repo / 'build-bandlimited-dna-v1'
a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, commands=[], phase=a.phase)
try:
    names = set()
    for switches in (['ls-files', '-z'], ['ls-files', '--others', '--exclude-standard', '-z']):
        names.update(subprocess.check_output(['git'] + switches, cwd=repo).decode('utf-8').split('\0'))
    for name in sorted(n for n in names if n and (Path(n).suffix in ('.c', '.h', '.cmake', '.in') or n.endswith('CMakeLists.txt'))):
        dest = a.out / 'exact_sources' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dest)
        r['sources'][name] = sha(repo / name)
    shutil.copy2(__file__, a.out / 'executed_build.py')
    commands = [['cmake', '-S', repo / 'experiments/bandlimited_dna_v1', '-B', build,
                 '-G', 'Visual Studio 17 2022', '-A', 'x64'],
                ['cmake', '--build', build, '--config', 'Release', '--parallel', '2']]
    if a.phase == 'focused':
        commands[-1] += ['--target', 'bandlimited_load_checks', 'bandlimited_render_checks',
                         'bandlimited_drive_checks', 'sound_dna_bandlimited_export', 'sound_dna_legacy_export']
    commands += [['ctest', '--test-dir', build, '-C', 'Release', '--output-on-failure',
                  '--output-junit', a.out / 'ctest.xml']]
    if a.phase == 'focused':
        commands[-1] += ['-R', '^bandlimited_']
    for argv in commands:
        argv = list(map(str, argv))
        start = time.perf_counter()
        done = subprocess.run(argv, cwd=repo, capture_output=True, timeout=900)
        log = a.out / ('command_%02d.log' % len(r['commands']))
        log.write_bytes(done.stdout + done.stderr)
        row = dict(argv=argv, exit_code=done.returncode, seconds=time.perf_counter()-start,
                   log=log.name, sha256=sha(log))
        r['commands'].append(row)
        save(a.out / 'report.json', r)
        print(row, flush=True)
        if done.returncode:
            raise RuntimeError(str(log))
    shutil.copy2(build / 'CMakeCache.txt', a.out / 'CMakeCache.txt')
    r['result'] = 'passed'
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out / 'report.json', r)
