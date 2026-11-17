"""Prepare editable real-A startup examples; does not launch apps or alter banks."""
import argparse
import base64
import json
from pathlib import Path
import sys


def write_recipe(repo,value,output):
    from vehicle_controller.native import Bridge,Engine
    from vehicle_controller.recipe import create,validate
    from vehicle_controller.event_profiles import document
    bridge=Bridge(repo);control,_=bridge.initial(0);control['events']['enabled']=1
    overrides={row['kind']:document(json.loads(Path(row['package']).read_text(encoding='utf-8'))) for row in value['projects']}
    recipe=create(bridge,0,control,'踏板驾驶',overrides);validate(bridge,recipe)
    # Verify adoption without generating sound or opening a device/window.
    with Engine(bridge,0,overrides) as engine:engine.set(control)
    path=Path(output)/'vehicle_startup.recipe.json';path.write_text(json.dumps(recipe,ensure_ascii=False,indent=2),encoding='utf-8')
    value['recipe']=str(path)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('E:/VehicleSoundLab/designs/events'))
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import soundfile as sf
    from event_authoring.audio import read,sha
    from event_designer.workspace import EventWorkspace
    repo=Path(__file__).resolve().parents[1];source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    x,sr,provenance=read(source,35,38.2);clip=a.output/'A_start_context.wav';sf.write(clip,x,sr,subtype='FLOAT')
    payload=base64.b64encode(clip.read_bytes()).decode();workspace=EventWorkspace(repo,a.root);result=[]
    for kind,name,seconds,gated in [('crank','A 启动早期混合纹理候选',[1.65,2.12],True),
                                    ('catch','A 接火混合声学候选',[2.22,3.02],False)]:
        current=workspace.create(dict(filename=clip.name,audio=payload,kind=kind,viewpoint='cabin'))
        current=workspace.analyze(dict(id=current['id'],name=name,kind=kind,viewpoint='cabin',seconds=seconds,
            background_seconds=[0,1.2],gated=gated,context='Approved A interior startup, original crop35.0–38.2s. Mixed acoustic observation; physical source and RPM not identified.'))
        folder,value=workspace.load(current['id']);value['document']['source_clip_origin']=provenance
        workspace.commit(folder,value,'补充原素材来源')
        current=workspace.render(dict(id=current['id']))
        result.append(dict(id=current['id'],name=name,kind=kind,folder=str(folder),
            package=str(folder/current['last_version']/'parameters.json'),hearing_accepted=False))
    value=dict(schema='vsl.event-designer-examples/1',original_source_sha256=sha(source),projects=result,
        changed_global_bank=False,started_persistent_UI=False)
    write_recipe(repo,value,a.output)
    (a.output/'examples.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
