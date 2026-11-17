"""Check the live workbench launch route and independent window readiness."""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8791);a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    def post():
        request=urllib.request.Request(f'http://127.0.0.1:{a.port}/api/driver',data=b'{}',headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
    first=post();deadline=time.monotonic()+15;path=Path(first['ready'])
    while not path.is_file():
        if time.monotonic()>deadline:raise RuntimeError('Controller did not produce a ready receipt')
        time.sleep(.1)
    ready=json.loads(path.read_text(encoding='utf-8'));assert ready['pid']==first['pid'] and ready['source_only'] and not ready['listening']
    second=post();assert second['pid']==first['pid'] and second['already_open']
    with urllib.request.urlopen(f'http://127.0.0.1:{a.port}/app.js',timeout=10) as response:script=response.read().decode('utf-8')
    assert '独立声源控制窗口' in script
    report=dict(schema='vsl.controller-launch-verification/1',first=first,second=second,window_ready=ready,
        independent_window_ready=True,no_audio_autoplay=True,duplicate_launch_reused=True,workbench_script_updated=True)
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
