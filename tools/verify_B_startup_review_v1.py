"""Bounded, owned HTTP service for the B startup review; never restart the app."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
from research_archive_v1 import load,save


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(a.review)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        script=repo/'tools/verify_B_startup_review_v1.cjs'
        result=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),
            f'http://127.0.0.1:{server.server_address[1]}/index.html',str(a.output/'browser')],
            capture_output=True,timeout=120,creationflags=0x08000000)
        (a.output/'stdout.log').write_bytes(result.stdout);(a.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=load(a.output/'browser/report.json');assert browser['result']=='passed'
    for name in ('verify_B_startup_review_v1.py','verify_B_startup_review_v1.cjs'):
        shutil.copy2(repo/'tools'/name,a.output/name)
    save(a.output/'report.json',dict(result='passed',browser=browser,own_service_closed=True,
        persistent_service_restarted=False,audio_muted=True,timbre_accepted=False,goal_complete=False))
    print(dict(result='passed',own_service_closed=True),flush=True)


if __name__=='__main__':main()
