"""Check source-context authoring without changing fitted sound or runtime DSP."""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile
import numpy as np
import soundfile as sf
from event_authoring.audio import sha
from event_authoring.scan import neighborhood,peaks
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json
from sound_designer.server import create_server


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    workspace=EventWorkspace(repo,a.output/'known-projects');known=[]
    rate=48000;t=np.arange(rate*2)/rate
    carrier=np.sin(2*np.pi*1500*t)+.3*np.sin(2*np.pi*4800*t)
    envelope=np.ones(len(t))*.05;envelope[(t>=.8)&(t<1.0)]=.2
    for antiphase in (False,True):
        original=np.stack([carrier*envelope,carrier*envelope*(-1 if antiphase else 1)],axis=1)
        file=a.output/('antiphase.wav' if antiphase else 'inphase.wav');sf.write(file,original,rate,subtype='FLOAT')
        project=workspace.create(dict(filename=file.name,audio=base64.b64encode(file.read_bytes()).decode(),kind='afterfire'))
        data=dict(id=project['id'],seconds=[.8,1.],background_seconds=[.2,.4],following_background_seconds=[1.2,1.4])
        project=workspace.probe_context(data);report=project['context_probe'];folder=workspace.root/project['id']
        source,_=sf.read(folder/'master.wav',always_2d=True)
        expected=10*np.log10(np.mean(source[38400:48000]**2)/np.mean(source[9600:19200]**2))
        assert abs(report['backgrounds'][0]['full_contrast_db']-expected)<1e-11
        assert abs(expected-12.041199826559248)<1e-6
        assert project['context_matches_selection'] and project['document'] is None
        audio,_=sf.read(folder/project['context_run']/'original.wav',always_2d=True)
        monitor,_=sf.read(folder/project['context_run']/'monitor.wav',always_2d=True)
        assert np.array_equal(audio,source[9600:67200]) and np.array_equal(monitor,audio*.25)
        # Scan/detection retains channel energy instead of stereo cancellation.
        found=peaks(source,0);screen=neighborhood(source,40000)
        known.append(dict(antiphase=antiphase,contrast_db=expected,detected=found,screen=screen))
        prior=(folder/'project.json').read_bytes();history=len(project['history'])
        invalid=[]
        for after in ([.9,1.1],[1.8,2.1],[1.2,1.2],[True,1.3],[float('nan'),1.3]):
            try:workspace.probe_context(dict(data,following_background_seconds=after))
            except ValueError:invalid.append(str(after))
            else:raise AssertionError('Invalid following background admitted')
            assert (folder/'project.json').read_bytes()==prior and len(workspace.view(project['id'])['history'])==history
        assert len(invalid)==5
    assert known[0]['detected']==known[1]['detected'] and known[0]['screen']==known[1]['screen']
    parameter=workspace.create(dict(preset='catch'))
    try:workspace.probe_context(dict(id=parameter['id'],seconds=[.8,1.],background_seconds=[.2,.4],following_background_seconds=[1.2,1.4]))
    except ValueError:pass
    else:raise AssertionError('Parameter-only project admitted as an audio reference')
    master=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    original,rate=sf.read(master,start=35*48000,stop=round(40.5*48000),always_2d=True)
    fixture=a.output/'A_35_to_40_5_original.wav';sf.write(fixture,original,rate,subtype='FLOAT')
    server=create_server(repo,a.output/'browser-projects',0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    ui=a.output/'ui';ui.mkdir();script=repo/'tools/verify_event_context_ui_v1.cjs';shutil.copy2(script,ui/script.name)
    try:
        run=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(ui),str(fixture),
             'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=180,creationflags=0x08000000)
        (ui/'stdout.log').write_bytes(run.stdout);(ui/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=json.loads((ui/'report.json').read_text(encoding='utf-8'))
    ws=EventWorkspace(repo,a.output/'browser-projects/events');project=ws.view(browser['project_id'])
    exports=list((ws.root/project['id']).glob('*/source-context.json'));assert exports
    for file in exports:
        folder=file.parent
        with zipfile.ZipFile(folder/'event-design.zip') as archive:assert json.loads(archive.read(file.name))==json.loads(file.read_text(encoding='utf-8'))
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        assert all(sha(folder/name)==digest for name,digest in manifest['files'].items())
    report=project['context_probe'];folder=ws.root/project['id'];audio,_=sf.read(folder/'master.wav',always_2d=True)
    event=audio[round(report['event_seconds'][0]*48000):round(report['event_seconds'][1]*48000)]
    errors=[]
    for row in report['backgrounds']:
        b=row['source'];background=audio[b['first_frame']:b['last_frame']]
        independent=10*np.log10(np.mean(event*event)/np.mean(background*background))
        errors.append(abs(independent-row['full_contrast_db']))
    assert max(errors)<1e-10
    exact=a.output/'exact_sources';exact.mkdir()
    files=[Path(__file__),script,repo/'tools/inspect_event_timeline_v1.py',repo/'tools/scan_approved_event_region.py',
           repo/'tools/event_authoring/scan.py',repo/'tools/event_designer/context.py',
           repo/'tools/event_designer/workspace.py',repo/'tools/event_designer/package.py',repo/'tools/sound_designer/server.py',
           repo/'tools/sound_designer/web/events.js',repo/'tools/sound_designer/web/event_player.js',repo/'tools/sound_designer/web/events.html',repo/'tools/sound_designer/web/events.css']
    for file in files:
        target=exact/file.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    result=dict(schema='vsl.event-context-workbench-verification/1',result='passed',known=known,browser=browser,
                independent_material_contrast_error_db=max(errors),invalid_inputs_preserve_project=True,
                source_context_PCM_exact=True,owned_server_closed=True,source_C_changed=False,
                no_new_download=True,no_formal_profile_promotion=True,timbre_accepted=False,goal_complete=False)
    write_json(a.output/'report.json',result);print(json.dumps(dict(result='passed',output=str(a.output))))


if __name__=='__main__':main()
