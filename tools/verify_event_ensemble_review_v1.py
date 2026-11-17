"""Check nine comparison tracks, including an actual16ms reference, in Chrome."""
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    script=(repo/'tools/verify_short_event_review_v1.cjs').read_text(encoding='utf-8')
    replacements=[('assert.equal(rows.length,8)','assert.equal(rows.length,9)'),
        ("await select(index);await page.locator('audio').evaluate(a=>a.currentTime=.1);\n   await page.waitForFunction(()=>{const a=document.querySelector('audio');return !a.seeking&&Math.abs(a.currentTime-.1)<.01;});",
         "await select(index);const target=Math.min(.1,row.frames/48000*.4);await page.locator('audio').evaluate((a,t)=>a.currentTime=t,target);\n   await page.waitForFunction(t=>{const a=document.querySelector('audio');return !a.seeking&&Math.abs(a.currentTime-t)<.001;},target);"),
        ("await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});",
         "for(const img of await page.locator('img').all())assert(await img.evaluate(i=>i.complete&&i.naturalWidth>0));\n  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));\n  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});"),
        ('eight_track_hash_decode_seek','nine_track_hash_decode_seek')]
    for old,new in replacements:
        assert script.count(old)==1,old;script=script.replace(old,new)
    browser=args.output/'executed_browser.cjs';browser.write_text(script,encoding='utf-8')
    shutil.copy2(__file__,args.output/'executed_verification.py')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(args.review)))
    thread=threading.Thread(target=server.serve_forever);thread.start();report=dict(result='running',timbre_accepted=False)
    try:
        run=subprocess.run([str(node),str(browser),str(node.parents[1]/'node_modules'),
            f'http://127.0.0.1:{server.server_address[1]}/index.html',str(args.output/'browser')],
            capture_output=True,timeout=120,creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(run.stdout);(args.output/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
        report.update(result='passed',browser=load(args.output/'browser/report.json'))
    except Exception as error:report.update(result='failed',error=repr(error));raise
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
        report.update(own_service_closed=not thread.is_alive(),persistent_service_restarted=False)
        save(args.output/'report.json',report)
    assert not thread.is_alive();print(dict(result='passed',tracks=9,own_service_closed=True),flush=True)


if __name__=='__main__':main()
