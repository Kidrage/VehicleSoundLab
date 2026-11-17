"""Catalog identity rejection/ownership tests in an isolated input copy."""
import argparse
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

from research_archive_v1 import load,save,sha
from vehicle_controller import catalog_assets,recipe,take
from vehicle_controller.native import Bridge,Engine


def probe(bridge):
    result=[]
    for row in bridge.catalog:
        control=bridge.initial(row['id'])[0]
        audio=hashlib.sha256();native=hashlib.sha256()
        with Engine(bridge,row['id']) as engine:
            engine.set(control)
            for _ in range(25):
                audio.update(engine.process(240))
                native.update(bytes(engine.stems)[:240*bridge.channels()*4])
        result.append(dict(id=row['id'],monitor_sha256=audio.hexdigest(),native_sha256=native.hexdigest()))
    return result


def refused(call):
    try:call()
    except (ValueError,RuntimeError) as error:return str(error)
    raise AssertionError('Expected identity refusal')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,out/'executed_verification.py')
    repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab')
    frozen=data/'baselines/A_exterior_startup_v1/delivery1/repo/tools'
    previous=data/'baselines/start_idle_lifecycle_v1/delivery1/evidence/C3'
    # A genuinely separate interpreter imports only the frozen V12 modules.
    script=out/'frozen_probe.py'
    script.write_text('''import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import take,recipe
b=Bridge(Path(sys.argv[2]));rows=[]
for row in b.catalog:
 c=b.initial(row['id'])[0];a=hashlib.sha256();s=hashlib.sha256()
 with Engine(b,row['id']) as e:
  e.set(c)
  for _ in range(25):
   a.update(e.process(240));s.update(bytes(e.stems)[:240*b.channels()*4])
 rows.append(dict(id=row['id'],monitor_sha256=a.hexdigest(),native_sha256=s.hexdigest()))
old=take.read(Path(sys.argv[3])/'idle_layer/lifecycle.vsltake.json',b)
recipe.validate(b,json.loads((Path(sys.argv[3])/'controller-preset.json').read_text(encoding='utf-8')))
Path(sys.argv[4]).write_text(json.dumps(dict(rows=rows,old_take_schema=old['schema'],module=take.__file__)),encoding='utf-8')
''',encoding='utf-8')
    checked=subprocess.run([sys.executable,str(script),str(frozen),str(repo),str(previous),str(out/'frozen-probe.json')],
        cwd=repo,capture_output=True,creationflags=0x08000000)
    (out/'frozen-stdout.log').write_bytes(checked.stdout);(out/'frozen-stderr.log').write_bytes(checked.stderr)
    assert checked.returncode==0,checked.stderr.decode(errors='replace')
    reference=load(out/'frozen-probe.json')
    assert Path(reference['module']).resolve().is_relative_to(frozen.resolve())
    current=Bridge(repo)
    assert probe(current)==reference['rows'] and len(reference['rows'])==12
    rejected_old=refused(lambda:take.read(previous/'idle_layer/lifecycle.vsltake.json',current))
    refused(lambda:recipe.validate(current,load(previous/'controller-preset.json')))
    mirror=out/'isolated-inputs';mirror.mkdir()
    for name in current.catalog_assets['files']:
        target=mirror/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
    library=current.path.resolve()
    original_cwd=Path.cwd()
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    try:
        os.chdir(mirror)
        bridge=Bridge(mirror,library=library)
        control=bridge.initial(0)[0]
        saved=recipe.create(bridge,0,control,'固定转速',{})
        value=take.create(bridge,0,control);value['frames']=240
        path=out/'new.take.json';take.save(path,value)
        assert take.read(path,bridge)==value
        recipe.validate(bridge,saved)
        assert len(bridge.catalog_assets['files'])==92
        cases=[]
        for name in catalog_assets.LEGACY_INPUTS:
            file=mirror/name;before=file.read_bytes()
            try:
                file.write_bytes(before+b'\n')
                assert catalog_assets.inventory(mirror)[0]!=bridge.catalog_assets_sha256
                with patch.object(bridge,'open',side_effect=AssertionError('must refuse before C opens')):
                    message=refused(lambda:Engine(bridge,0))
                refused(lambda:take.read(path,bridge));refused(lambda:recipe.validate(bridge,saved))
                refused(lambda:take.create(bridge,0,control));refused(lambda:recipe.create(bridge,0,control,'固定转速',{}))
                refreshed=Bridge(mirror,library=library)
                refused(lambda:take.read(path,refreshed));refused(lambda:recipe.validate(refreshed,saved))
                cases.append(dict(file=name,stale_open_and_read_refused=True,new_bridge_old_documents_refused=True,message=message))
            finally:file.write_bytes(before)
        for mutation in ('missing_manifest','missing_F2_entry','altered_digest'):
            bad=deepcopy(value)
            if mutation=='missing_manifest':bad.pop('catalog_assets')
            elif mutation=='missing_F2_entry':
                del bad['catalog_assets']['files'][catalog_assets.LEGACY_INPUTS[0]]
                bad['catalog_assets_sha256']=catalog_assets.digest(bad['catalog_assets'])
            else:bad['catalog_assets_sha256']='0'*64
            take.save(out/(mutation+'.json'),bad)
            refused(lambda:take.read(out/(mutation+'.json'),bridge))
        file=mirror/catalog_assets.LEGACY_INPUTS[0];before=file.read_bytes()
        opened=[];closed=[];real_open=bridge.open;real_close=bridge.close
        def change_during_open(selection):
            handle=real_open(selection);opened.append(handle);file.write_bytes(before+b'\n');return handle
        def close(handle):closed.append(handle);real_close(handle)
        try:
            with patch.object(bridge,'open',side_effect=change_during_open),patch.object(bridge,'close',side_effect=close):
                refused(lambda:Engine(bridge,0))
            assert opened==closed and len(opened)==1
        finally:file.write_bytes(before)
        # Existing owned C voices survive file changes. No hashing enters process.
        with Engine(bridge,0) as a,Engine(bridge,0) as b:
            a.set(control);b.set(control)
            assert a.process(240)==b.process(240)
            try:
                file.write_bytes(before+b'\n')
                with patch('vehicle_controller.catalog_assets.inventory',side_effect=AssertionError('audio must not hash files')):
                    assert a.process(480)==b.process(480)
            finally:file.write_bytes(before)
        file.unlink()
        try:refused(lambda:catalog_assets.inventory(mirror))
        finally:file.write_bytes(before)
        assert catalog_assets.inventory(mirror)[0]==bridge.catalog_assets_sha256
        report.update(result='passed',old12_catalog_6000frame_probes_exact=True,
            old_take8_frozen_player_loads=True,new_reader_refuses_old_take=True,old_refusal=rejected_old,
            new_take_schema=value['schema'],new_preset_schema=saved['schema'],catalog_files=92,
            per_F2_rejections=cases,tampered_manifest_cases=3,around_load_refusal_closes_handle=True,
            missing_file_refused=True,owned_audio_no_hash_and_exact=True,
            catalog_assets_sha256=bridge.catalog_assets_sha256,only_isolated_inputs_modified=True)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:
        os.chdir(original_cwd);save(out/'report.json',report)


if __name__=='__main__':main()
