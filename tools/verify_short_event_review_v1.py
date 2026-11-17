"""Verify the short-event review on an owned temporary static service."""
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(args.review)))
    thread=threading.Thread(target=server.serve_forever);thread.start()
    report=dict(result='running',timbre_accepted=False)
    try:
        for name in ('verify_short_event_review_v1.py','verify_short_event_review_v1.cjs'):
            shutil.copy2(repo/'tools'/name,args.output/name)
        result=subprocess.run([str(node),str(repo/'tools/verify_short_event_review_v1.cjs'),
            str(node.parents[1]/'node_modules'),f'http://127.0.0.1:{server.server_address[1]}/index.html',str(args.output/'browser')],
            capture_output=True,timeout=120,creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(result.stdout);(args.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
        report=dict(result='passed',browser=load(args.output/'browser/report.json'),timbre_accepted=False)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report.update(own_service_closed=not thread.is_alive(),persistent_service_restarted=False)
        save(args.output/'report.json',report)
    assert not thread.is_alive();print(dict(result=report['result'],own_service_closed=True),flush=True)
