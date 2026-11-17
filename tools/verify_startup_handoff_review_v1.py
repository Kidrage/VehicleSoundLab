"""Own a bounded test server and browser; do not restart any persistent service."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading

from event_designer.package import write_json


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(a.review)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([str(node),str(repo/'tools/verify_startup_handoff_review_v1.cjs'),
            str(node.parents[1]/'node_modules'),f'http://127.0.0.1:{server.server_address[1]}/index.html',str(a.output/'browser')],
            capture_output=True,timeout=120,creationflags=0x08000000)
        (a.output/'stdout.log').write_bytes(result.stdout);(a.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    import json
    browser=json.loads((a.output/'browser/report.json').read_text(encoding='utf-8'))
    assert browser['result']=='passed'
    for name in ('verify_startup_handoff_review_v1.py','verify_startup_handoff_review_v1.cjs'):
        shutil.copy2(repo/'tools'/name,a.output/name)
    write_json(a.output/'report.json',dict(result='passed',browser=browser,own_service_closed=True,
        persistent_service_restarted=False,audio_muted=True,timbre_accepted=False))
    print(dict(result='passed',own_service_closed=True),flush=True)
