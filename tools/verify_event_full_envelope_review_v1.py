"""Bounded muted browser check for the ten-track complete-event comparison."""
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    script = (repo/'tools/verify_low_mid_event_review_v1.cjs').read_text(encoding='utf-8')
    for old, new, count in [
        ('assert.equal(tracks.length, 9)', 'assert.equal(tracks.length, 10)', 1),
        ('await select(6)', 'await select(5)', 1),
        ('await select(7)', 'await select(8)', 2),
        ('[0, 7, 1]', '[0, 8, 1]', 1),
        ('a.duration - .1', 'a.duration - .31', 1),
        ('nine_hashes_and_decodes', 'ten_hashes_and_decodes', 1),
        ('short_100ms_blob_seek', 'short_310ms_blob_seek', 1)]:
        assert script.count(old) == count, (old, script.count(old))
        script = script.replace(old, new)
    browser = args.output/'executed_browser.cjs'
    browser.write_text(script, encoding='utf-8')
    shutil.copy2(__file__, args.output/'executed_verification.py')
    node = Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(args.review)))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([str(node), str(browser), str(node.parents[1]/'node_modules'),
            f'http://127.0.0.1:{server.server_address[1]}/index.html', str(args.output/'browser')],
            capture_output=True, timeout=120, creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(result.stdout)
        (args.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    report = load(args.output/'browser/report.json')
    assert report['result'] == 'passed' and not thread.is_alive()
    save(args.output/'verification.json', dict(result='passed', browser=report,
        own_service_closed=True, persistent_service_restarted=False, audio_muted=True,
        timbre_accepted=False))
    print(dict(result='passed', tracks=10), flush=True)


if __name__ == '__main__':
    main()
