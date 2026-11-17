"""Bounded muted browser verification of ten same-gain review tracks."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
from verify_startup_handoff_review_v1 import Quiet
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    script=(repo/'tools/verify_startup_contour_review_v1.cjs').read_text(encoding='utf-8')
    # Reuse the existing hash/decode/Blob/seek/playing/download/mobile verifier,
    # with the complete startup pair at indices8/9 in this ten-track page.
    for old,new in [('headless:true','headless:true,args:["--mute-audio"]'),
                    ('tracks.length,6','tracks.length,10'),('select(4)','select(8)'),('select(5)','select(9)'),
                    ('six_hashes_and_decodes','ten_hashes_and_decodes')]:
        assert old in script;script=script.replace(old,new)
    executed=args.output/'executed_browser.cjs';executed.write_text(script,encoding='utf-8')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(args.review)))
    thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        run=subprocess.run([str(node),str(executed),str(node.parents[1]/'node_modules'),
            'http://127.0.0.1:'+str(server.server_address[1])+'/index.html',str(args.output/'browser')],
            capture_output=True,timeout=120,creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(run.stdout);(args.output/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive();report=load(args.output/'browser/report.json')
    assert report['result']=='passed' and len(report['decoded'])==10
    save(args.output/'verification.json',dict(result='passed',browser=report,own_service_closed=True,
        persistent_service_restarted=False,audio_muted=True,timbre_accepted=False))
    shutil.copy2(__file__,args.output/'executed_verification.py')
    print(dict(result='passed',tracks=10,own_service_closed=True),flush=True)


if __name__=='__main__':main()
