"""Own a bounded muted nine-track review check; leave persistent services alone."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading

from research_archive_v1 import load, save
from verify_startup_handoff_review_v1 import Quiet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for name in ('verify_low_mid_event_review_v1.py', 'verify_low_mid_event_review_v1.cjs'):
        shutil.copy2(repo/'tools'/name, args.output/name)
    node = Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(args.review)))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        run = subprocess.run([str(node), str(args.output/'verify_low_mid_event_review_v1.cjs'),
            str(node.parents[1]/'node_modules'), f'http://127.0.0.1:{server.server_address[1]}/index.html',
            str(args.output/'browser')], capture_output=True, timeout=120, creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(run.stdout)
        (args.output/'stderr.log').write_bytes(run.stderr)
        assert run.returncode == 0, run.stderr.decode(errors='replace')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    browser = load(args.output/'browser/report.json')
    assert browser['result'] == 'passed' and not thread.is_alive()
    save(args.output/'verification.json', dict(result='passed', browser=browser,
        own_service_closed=True, persistent_service_restarted=False,
        audio_muted=True, timbre_accepted=False))
    print(dict(result='passed', tracks=9, own_service_closed=True), flush=True)


if __name__ == '__main__':
    main()
