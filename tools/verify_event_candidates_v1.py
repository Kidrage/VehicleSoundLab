"""Fixed-rule discovery, material evidence, existing C sound and actual web UI."""
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
from event_authoring.scan import scan_file
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json
from sound_designer.server import create_server


def imported(workspace,path,kind='afterfire'):
    return workspace.create(dict(filename=path.name,audio=base64.b64encode(path.read_bytes()).decode(),
                                 kind=kind,viewpoint='cabin'))


def unchanged_on_error(workspace,project,data):
    path=workspace.root/project['id']/'project.json';before=path.read_bytes()
    try:workspace.use_candidate(data)
    except ValueError as error:
        assert path.read_bytes()==before
        return str(error)
    raise AssertionError('Invalid candidate accepted')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab')
    evidence=root/'references/analysis/A_exterior_event_v1'
    baseline=json.loads((evidence/'scan1/report.json').read_text(encoding='utf-8'))
    assert sha(Path(baseline['source']))==baseline['source_sha256']
    material=scan_file(baseline['source'],baseline['requested_ranges'])
    expected=[{k:v for k,v in row.items() if k!='source_id'} for row in baseline['candidates']]
    assert material['candidates']==expected and material['blocks']==baseline['blocks']
    assert len(expected)==92 and material['both_above_3db']==1
    # Independent PCM-window powers for all 92 material candidates.
    errors=[]
    with sf.SoundFile(baseline['source']) as file:
        for row in material['candidates']:
            powers={}
            for key in ('event','before','after'):
                lo,hi=[round(v*48000) for v in row[key+'_seconds']]
                file.seek(lo);audio=file.read(hi-lo,always_2d=True,dtype='float64')
                powers[key]=float(np.mean(audio*audio))
            for key in ('before','after'):
                errors.append(abs(10*np.log10(powers['event']/powers[key])-row['contrast_db'][key]))
    assert max(errors)<1e-11
    known=[];rate=48000;rng=np.random.default_rng(5823);t=np.arange(3*rate)/rate
    # Broadband event with known channel power symmetry, without stereo fold.
    x=rng.normal(0,.002,len(t))*(1+50*np.exp(-.5*((t-1.4)/.006)**2))
    for sign in (1,-1):
        path=a.output/('inphase.wav' if sign==1 else 'antiphase.wav')
        sf.write(path,np.stack([x,sign*x],axis=1),rate,subtype='FLOAT');known.append(scan_file(path))
    assert known[0]==known[1] and known[0]['both_above_3db']>=1
    silence=a.output/'silence.wav';sf.write(silence,np.zeros(rate),rate,subtype='FLOAT')
    assert not scan_file(silence)['candidates']
    for bad in ([[0,4]],[[True,2]],[[float('nan'),2]],[[1,1]],[[0,2],[1,3]],[]):
        try:scan_file(a.output/'inphase.wav',bad)
        except ValueError:pass
        else:raise AssertionError('Invalid scan range admitted')
    wrong=a.output/'wrong-rate.wav';sf.write(wrong,np.zeros(44100),44100,subtype='FLOAT')
    try:scan_file(wrong)
    except ValueError:pass
    else:raise AssertionError('Non-master sample rate admitted')
    workspace=EventWorkspace(repo,a.output/'projects')
    fixture=evidence/'timeline1/A_346_context/original.wav'
    project=imported(workspace,fixture);project=workspace.scan_candidates(dict(id=project['id']))
    assert len(project['candidate_scan']['candidates'])==2 and project['candidate_scan']['both_above_3db']==1
    assert project['document'] is None
    request=dict(id=project['id'],scan_run=project['scan_run'],candidate_index=1)
    project=workspace.use_candidate(request);folder=workspace.root/project['id']
    assert project['context_matches_selection'] and project['document'] is None
    assert not project['context_probe']['physical_identity_confirmed']
    assert project['selection']==[4.695,4.795]
    source,_=sf.read(folder/'master.wav',always_2d=True)
    original,_=sf.read(folder/project['context_run']/'original.wav',always_2d=True)
    assert np.array_equal(original,source[round(4.37*rate):round(5.08*rate)])
    invalid=[unchanged_on_error(workspace,project,dict(request,candidate_index=value))
             for value in (-1,True,2,1.5,'1')]
    invalid.append(unchanged_on_error(workspace,project,dict(request,scan_run='scan_stale')))
    report_path=folder/project['scan_run']/'report.json';raw=report_path.read_bytes()
    report_path.write_bytes(raw+b'\n')
    try:invalid.append(unchanged_on_error(workspace,project,request))
    finally:report_path.write_bytes(raw)
    before=deepcopy(project);project=workspace.scan_candidates(dict(id=project['id']))
    assert project['selection']==before['selection'] and not project.get('selected_candidate')
    invalid.append(unchanged_on_error(workspace,project,request))
    parameter=workspace.create(dict(preset='catch'))
    try:workspace.scan_candidates(dict(id=parameter['id']))
    except ValueError:pass
    else:raise AssertionError('Source-free parameter project scanned')
    # Actual accepted-structure C event preview is bit-identical after scans/selections.
    with sf.SoundFile(root/'references/clean/A_decoded_float.wav') as file:
        file.seek(35*rate);startup=file.read(round(5.5*rate),always_2d=True)
    startup_file=a.output/'startup-original.wav';sf.write(startup_file,startup,rate,subtype='FLOAT')
    p=imported(workspace,startup_file,'catch')
    p=workspace.analyze(dict(id=p['id'],seconds=[2.22,3.02],background_seconds=[0,1.2]))
    assert p['document'];p=workspace.render(dict(id=p['id']));pf=workspace.root/p['id']
    old_document=deepcopy(p['document']);old_controls=deepcopy(p['controls'])
    old_audio,_=sf.read(pf/p['last_version']/'synthesis.wav',dtype='float32')
    p=workspace.scan_candidates(dict(id=p['id']));assert p['candidate_scan']['candidates']
    p=workspace.use_candidate(dict(id=p['id'],scan_run=p['scan_run'],candidate_index=0))
    assert p['document']==old_document and p['controls']==old_controls and not p['preview_stale']
    p=workspace.render(dict(id=p['id']));version=pf/p['last_version']
    new_audio,_=sf.read(version/'synthesis.wav',dtype='float32');assert np.array_equal(old_audio,new_audio)
    bundle=json.loads((version/'parameters.json').read_text(encoding='utf-8'))
    assert bundle['candidate_scan']['matches_current_selection']
    assert not bundle['source_context']['matches_model_event_and_before_background']
    assert not bundle['candidate_scan']['physical_identity_confirmed']
    with zipfile.ZipFile(version/'event-design.zip') as archive:
        assert json.loads(archive.read('candidate-scan.json'))==bundle['candidate_scan']
    manifest=json.loads((version/'manifest.json').read_text(encoding='utf-8'))
    assert all(sha(version/name)==digest for name,digest in manifest['files'].items())
    server=create_server(repo,a.output/'browser-projects',0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    ui=a.output/'ui';ui.mkdir();script=repo/'tools/verify_event_candidates_ui_v1.cjs'
    try:
        run=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(ui),str(fixture),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=180,creationflags=0x08000000)
        (ui/'stdout.log').write_bytes(run.stdout);(ui/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=json.loads((ui/'report.json').read_text(encoding='utf-8'))
    exact=a.output/'exact_sources';exact.mkdir()
    files=[Path(__file__),script,*sorted((repo/'tools/event_authoring').glob('*.py')),
           *sorted((repo/'tools/event_designer').glob('*.py')),repo/'tools/sound_designer/server.py',
           repo/'tools/scan_approved_event_region.py',repo/'tools/sound_designer/web/event_candidates.js',
           repo/'tools/sound_designer/web/events.js',repo/'tools/sound_designer/web/events.html',repo/'tools/sound_designer/web/events.css']
    for file in files:
        target=exact/file.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
    result=dict(schema='vsl.event-candidates-verification/1',result='passed',
        material_scan_exact_to_frozen_pre_refactor=True,material_candidates=92,both_background_candidates=1,
        all_material_independent_contrast_error_db=max(errors),known_antiphase_exact=True,
        silence_no_candidates=True,invalid_selection_errors=invalid,
        source_context_PCM_exact=True,existing_C_PCM_bit_exact=True,
        candidate_evidence_in_JSON_ZIP=True,export_manifest_valid=True,browser=browser,
        owned_server_closed=True,no_formal_profile_promotion=True,timbre_accepted=False,goal_complete=False)
    write_json(a.output/'report.json',result);print(json.dumps(dict(result='passed',output=str(a.output))))


if __name__=='__main__':main()
