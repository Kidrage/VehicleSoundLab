"""Create editable projects from the approved A startup context, without normalizing."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_authoring.audio import sha
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json


def edit(project):
    return dict(id=project['id'],name=project['name'],kind=project['kind'],
        viewpoint=project['viewpoint'],context=project['context'],
        parameters=deepcopy(project['document']['parameters']),controls=deepcopy(project['controls']),
        analysis_scope=project['analysis_scope'],response_fit=project['response_fit'])


def build(repo,output,workspace_root):
    repo,output=Path(repo),Path(output);output.mkdir(parents=True,exist_ok=False)
    master=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    context,rate=sf.read(master,start=35*48000,stop=round(40.5*48000),always_2d=True)
    assert rate==48000
    source=output/'A_35_to_40_5_original.wav';sf.write(source,context,rate,subtype='FLOAT')
    workspace=EventWorkspace(repo,workspace_root);rows=[]
    source_fit=Path('E:/VehicleSoundLab/references/analysis/startup_timbre_v1')
    for kind,start,end,gated,name in [('crank',1.65,2.12,True,'A 启动早期纹理 · 频谱校准候选'),
                                    ('catch',2.22,3.02,False,'A 接火补充 · 频谱校准候选')]:
        p=workspace.create(dict(filename=source.name,audio=base64.b64encode(source.read_bytes()).decode(),
                                kind=kind,viewpoint='cabin'))
        p=workspace.analyze(dict(id=p['id'],name=name,seconds=[start,end],background_seconds=[0,1.2],
            gated=gated,response_fit='source-response-v1',analysis_scope=dict(mode='full'),
            context='Approved A original 35.0–40.5 s, unnormalized. Mixed cabin observation; starter/combustion/handling not physically separated. Engineering event slot; not measured RPM or accepted timbre.'))
        assert p['analysis'].get('status')!='analysis_only'
        expected=json.loads((source_fit/(kind+'1')/'profile.json').read_text(encoding='utf-8'))
        assert p['document']['parameters']==expected['parameters'],kind
        p['controls'].update(seconds=1.2,hold_seconds=end-start)
        p=workspace.render(edit(p));folder=workspace.root/p['id'];version=folder/p['last_version']
        assert p['reference_matches_model'] and p['response_fit']=='source-response-v1'
        assert p['document']['parameters']['noise_lowpass_hz']==10000
        raw,_=sf.read(version/'synthesis.wav',dtype='float32')
        reimport=workspace.create(dict(package=json.loads((version/'parameters.json').read_text(encoding='utf-8'))))
        assert reimport['response_fit']=='source-response-v1'
        reimport=workspace.render(edit(reimport))
        same,_=sf.read(workspace.root/reimport['id']/reimport['last_version']/'synthesis.wav',dtype='float32')
        assert np.array_equal(raw,same)
        exported=output/kind;shutil.copytree(version,exported)
        shutil.copy2(folder/p['analysis_run']/'reference-monitor.wav',exported/'reference-monitor.wav')
        rows.append(dict(kind=kind,id=p['id'],name=name,project_folder=str(folder),version=p['last_version'],
            parameters=str(version/'parameters.json'),profile_sha256=sha(version/'parameters.json'),
            direct_job_parameters_exact=True,source_free_import_pcm_exact=True,
            source_fit=p['document']['fit']['source_response_fit'],document=p['document'],controls=p['controls']))
    result=dict(schema='vsl.startup-timbre-projects/1',projects=rows,source=str(master),source_sha256=sha(master),
        context=str(source),context_sha256=sha(source),context_original_seconds=[35,40.5],
        monitor_gain=.25,independent_normalization=False,timbre_accepted=False,goal_complete=False)
    write_json(output/'report.json',result)
    return result
