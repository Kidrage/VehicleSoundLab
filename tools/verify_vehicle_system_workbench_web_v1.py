"""Bounded real browser: complete vehicle preset, versions and actual C adoption."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import threading
import traceback
import numpy as np
from sound_designer.server import create_server
from vehicle_controller import recipe
from vehicle_controller.native import Bridge, Engine
from research_archive_v1 import save, load, sha
from verify_vehicle_system_workbench_v1 import fixtures, binding


def run(out):
    out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    workspace,store,configuration=fixtures(repo,out);binding(repo,out)
    save(out/'configuration.json',configuration)
    script=repo/'tools/verify_vehicle_system_workbench_web_v1.cjs'
    shutil.copy2(__file__,out/'executed_verification.py');shutil.copy2(script,out/script.name)
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=create_server(repo,workspace.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(out),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=150,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(result.stdout);(out/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    presets=[load(out/(name+'.preset.json')) for name in ('browser','reloaded','after-invalid','historical')]
    assert all(value==presets[0] for value in presets)
    bridge=Bridge(repo);value=presets[0];recipe.validate(bridge,value)
    with Engine(bridge,value['catalog'],value['event_overrides'],value['startup_response'],
                value['event_policy'],value['dna_bank']) as engine:
        c=dict(value['control'],ignition=1,start_id=1);engine.set(c)
        pcm=b''.join(engine.process(480) for _ in range(200))
        assert np.any(np.frombuffer(pcm,dtype='<f4')) and engine.state()['event_started']>=4
    for name,expected in load(out/'source_binding.json').items():assert sha(repo/name)==expected,name
    save(out/'verification.json',dict(result='passed',browser=load(out/'report.json'),
        downloaded_full_preset_actual_C=True,bridge_sha256=bridge.sha256,preset_sha256=sha(out/'browser.preset.json'),
        own_service_closed=True,new_timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='passed',browser_and_native=True)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try:run(args.output)
    except Exception:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'failure-python.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
