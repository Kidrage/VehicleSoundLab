"""HTTP navigation and the exact shared DNA recipe contract; temporary server."""
import argparse
import json
from pathlib import Path
import threading
import subprocess
import shutil
from urllib.request import urlopen
from sound_designer.server import create_server
from sound_designer.workspace import Workspace
from sound_designer.vehicle_system import VehicleSystem,validate
from vehicle_controller import dna_bank,dna_character,recipe
from vehicle_controller.native import Bridge,Engine

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--browser',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];workspace=Workspace(repo,a.output/'workspace');system=VehicleSystem(workspace)
    fixture=workspace.root/'00000000000000000000000000000001';fixture.mkdir()
    shutil.copy2(repo/'voices/dna_bank_v1/Warm Additive.model',fixture/'base.model')
    (fixture/'project.json').write_text(json.dumps(dict(name='warm fixture',state='steady',viewpoint='exterior',params={})),encoding='utf-8')
    server=create_server(repo,workspace.root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    try:
        for route,expected in (('/','声音设计工作区'),('/index.html','音色工作台'),('/vehicles.html','车辆 DNA'),('/events.html','独立事件'),('/?project=legacy','音色工作台')):
            with urlopen(origin+route,timeout=15) as r:assert expected in r.read().decode('utf-8'),route
        with urlopen(origin+'/api/state-recipes/system',timeout=15) as r:meta=json.load(r)
        assert len(meta['dna_fields'])==6 and len(meta['dna_states'])==6
        settings=meta['defaults'];settings['dna']['line']=.73;settings['dna']['air_state'][2]=1.18
        assert validate(settings)['dna']==settings['dna']
        model=(repo/'voices/dna_bank_v1/Warm Additive.model').read_text(encoding='ascii')
        bank=dna_bank.create([dna_bank.anchor(model,'warm')],4000)
        preset,provenance=system.compile(bank,settings);assert preset['control']['dna']==settings['dna']
        bridge=Bridge(repo);recipe.validate(bridge,preset)
        with Engine(bridge,0,dna_bank=bank) as engine:engine.set(preset['control'])
        # Historical configuration is explicitly completed with unity rows.
        old={k:v for k,v in settings.items() if k!='dna'};assert validate(old)['dna']==dna_character.defaults()
        result=dict(schema='vsl.unified-dna-workbench-check/1',http_navigation=True,metadata=True,compiled_preset_roundtrip=True,old_configuration_defaults=True,source_effective_sha256=preset['source_effective_sha256'])
        if a.browser:
            runtime=Path(r'C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node')
            subprocess.run([str(runtime/'bin/node.exe'),str(repo/'tools/verify_dna_unified_web_v1.cjs'),str(runtime/'node_modules'),origin,str(a.output)],check=True,timeout=90)
            result['browser']=True
        (a.output/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:server.shutdown();server.server_close();thread.join(timeout=5)

if __name__=='__main__':main()
