"""Actual Windows handle controls; never start or stop the real producer."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from research_archive_v1 import save, sha
from native_clock_batch_v1.process import OriginalProcess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--producer-pid', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    r = dict(result='running', controls=[], sources={})
    try:
        for name in ('tools/check_native_clock_batch_process_v1.py', 'tools/native_clock_batch_v1/process.py'):
            dest = a.out / 'exact_sources' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / name, dest); r['sources'][name] = sha(dest)
        for name, pid, live in (('self', os.getpid(), True), ('original_producer', a.producer_pid, True),
                                ('missing_pid', 0xffffffff, False)):
            handle = OriginalProcess(pid)
            state = handle.state()
            assert state['live'] == live
            r['controls'].append(dict(name=name, **state)); handle.close()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1); raise SystemExit(7)'],
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        handle = OriginalProcess(child.pid)
        before = handle.state()
        assert before['live']
        assert child.wait(timeout=10) == 7
        after = handle.state()
        assert after['process_handle_available'] and not after['live'] and after['exit_code'] == 7
        handle.close()
        r['controls'].append(dict(name='retained_handle_after_actual_exit', before=before, after=after))
        r.update(result='native_clock_batch_actual_process_handle_controls_verified', all_controls_passed=True,
                 no_real_producer_start_stop_restart_or_mutation=True)
        save(a.out / 'report.json', r)
        print('BATCH_PROCESS_CONTROLS', len(r['controls']), 'PASS', flush=True)
    except BaseException as error:
        r.update(result='failed', error=repr(error)); save(a.out / 'report.json', r); raise


if __name__ == '__main__':
    main()
