"""Close an owned loopback service after real browser parameter export tests."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import threading
import traceback
import numpy as np
from sound_designer.server import create_server
from sound_designer import models
from vehicle_controller import dna_bank as dna,take
from vehicle_controller.native import Bridge,Engine
from startup_response_evidence_v1 import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    script=repo/'tools/verify_dna_controller_web_v1.cjs';shutil.copy2(script,a.output/script.name);shutil.copy2(__file__,a.output/'executed_verification.py')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=create_server(repo,a.output/'projects',0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        completed=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(a.output),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=150,creationflags=0x08000000)
        (a.output/'stdout.log').write_bytes(completed.stdout);(a.output/'stderr.log').write_bytes(completed.stderr)
        assert completed.returncode==0,completed.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=json.loads((a.output/'report.json').read_text(encoding='utf-8'));checks=[];bridge=Bridge(repo)
    for item in browser['exports']:
        folder=a.output/'projects'/item['project_id'];project=json.loads((folder/'project.json').read_text(encoding='utf-8'))
        bank=dna.read(a.output/(item['name']+'.dnabank.json'))
        m,base=models.read(folder/'base.model');expected=models.edit(m,base,project['params'],project['rows'],project['rho'])
        rendered=folder/project['driver_export']['version']/'voice.model';actual,actualbase=models.read(rendered)
        assert actualbase==base and all(np.array_equal(expected[k],actual[k]) for k in m)
        assert bank['anchors'][0]['sha256']==sha(rendered)
        with Engine(bridge,0,dna_bank=bank) as engine:
            engine.set(dict(engine.controls,mode=0,rpm=3000.,ignition=1,start_id=1))
            frames=[engine.process(480) for _ in range(150)]
            assert any(np.any(np.frombuffer(pcm,dtype='<f4')) for pcm in frames)
        checks.append(dict(name=item['name'],edited_model_exact=True,native_C_import=True,dna_bank_sha256=dna.digest(bank)))
    take.save(a.output/'verification.json',dict(result='passed',browser=browser,checks=checks,owned_service_closed=True,goal_complete=False,new_timbre_accepted=False))
    print(json.dumps(dict(result='passed',checks=checks)),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:
        import sys
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure-python.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
