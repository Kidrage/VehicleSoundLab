"""Real muted browser checks over two owned temporary servers."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading

from research_archive_v1 import load, save
from sound_designer.server import create_server
from verify_startup_handoff_review_v1 import Quiet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    assert load(args.evidence/'report.json')['result'] == 'passed'
    short = load(Path('E:/VehicleSoundLab/references/analysis/low_mid_event_scan_v1/C1/review/event-profile.json'))
    save(args.output/'fixture.json', dict(document=short))
    browser = args.output/'executed_browser.cjs'
    shutil.copy2(repo/'tools/verify_material_review_web_v1.cjs', browser)
    shutil.copy2(__file__, args.output/'executed_verification.py')
    node = Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    servers = [ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(args.evidence/'review'))),
               create_server(repo, args.output/'workspace', 0)]
    threads = [threading.Thread(target=server.serve_forever) for server in servers]
    for thread in threads:
        thread.start()
    failed=None
    try:
        result = subprocess.run([str(node), str(browser), str(node.parents[1]/'node_modules'), str(args.output),
            *['http://127.0.0.1:'+str(s.server_address[1]) for s in servers]],
            capture_output=True, timeout=120, creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(result.stdout)
        (args.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
    except Exception as error:
        failed=repr(error)
        raise
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)
        if failed:
            save(args.output/'verification.json',dict(result='failed',error=failed,
                own_servers_closed=all(not thread.is_alive() for thread in threads),
                goal_complete=False,timbre_accepted=False))
    checked = load(args.output/'report.json')
    assert checked['result'] == 'passed' and all(not t.is_alive() for t in threads)
    save(args.output/'verification.json', dict(result='passed', browser=checked,
        own_servers_closed=True, audio_muted=True, persistent_service_restarted=False,
        goal_complete=False, timbre_accepted=False))
    print('real review playback/download and workbench review/export display passed; owned servers closed', flush=True)


if __name__ == '__main__':
    main()
