"""Serve a bounded owned workbench and verify downloaded state banks in C."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import threading
import traceback
import numpy as np
from sound_designer.server import create_server
from vehicle_controller import dna_bank as dna
from vehicle_controller.native import Bridge, Engine
from research_archive_v1 import save, sha
from verify_state_recipe_workbench_v1 import fixtures, binding
from sound_designer.workspace import Workspace


def run(out):
    out.mkdir(parents=True, exist_ok=False);repo=Path(__file__).resolve().parents[1]
    binding(repo,out)
    script=repo/'tools/verify_state_recipe_workbench_web_v1.cjs'
    shutil.copy2(__file__,out/'executed_verification.py');shutil.copy2(script,out/script.name)
    workspace=Workspace(repo,out/'projects');ids=fixtures(workspace);save(out/'fixture_ids.json',ids)
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=create_server(repo,workspace.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(out),
            'http://127.0.0.1:'+str(server.server_address[1]),str(out/'fixture_ids.json')],
            cwd=repo,capture_output=True,timeout=150,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(result.stdout);(out/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    banks=[dna.read(out/(name+'.dnabank.json')) for name in ('browser','reloaded','after-invalid','historical')]
    assert all(bank==banks[0] for bank in banks)
    bridge=Bridge(repo)
    with Engine(bridge,0,dna_bank=banks[0]) as engine:
        engine.set(dict(engine.controls,mode=0,rpm=4000.,load=.6,ignition=1,start_id=1))
        pcm=b''.join(engine.process(480) for _ in range(200))
        assert np.any(np.frombuffer(pcm,dtype='<f4')) and engine.dna_state()['weight'][2]>.99
    save(out/'verification.json',dict(result='passed',browser=json.loads((out/'report.json').read_text(encoding='utf-8')),
        downloaded_parameters_actual_C=True,source_free_bank_sha256=dna.digest(banks[0]),bridge_sha256=sha(bridge.path),
        own_service_closed=True,goal_complete=False,new_timbre_accepted=False))
    print(json.dumps(dict(result='passed',browser_and_native=True)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:run(args.output)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure-python.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
