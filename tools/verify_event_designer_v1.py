"""Bounded verification of event authoring, actual C output, exports and UI."""
import argparse
import base64
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import traceback
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.audio import sha
    from event_authoring.model import synth,validate
    from event_authoring.native import Renderer
    from event_designer.workspace import EventWorkspace
    from sound_designer.server import create_server
    repo=Path(__file__).resolve().parents[1];report=dict(schema='vsl.event-designer-verification/1',goal_complete=False)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    def check(value,description):
        if not value:raise AssertionError(description)
    def upload(path):return dict(filename=path.name,audio=base64.b64encode(path.read_bytes()).decode())
    def edit(p,**kw):return dict(id=p['id'],name=p['name'],kind=p['kind'],viewpoint=p['viewpoint'],context=p['context'],
        parameters=deepcopy(p['document']['parameters']),controls=deepcopy(p['controls']),**kw)
    def refused(action,description):
        try:action()
        except (ValueError,TypeError,KeyError):return description
        raise AssertionError('Expected refusal: '+description)
    # Prescribed stereo source: shared 1 kHz decay plus independent low background.
    rng=np.random.default_rng(18911);t=np.arange(57600)/48000;age=np.maximum(t-.4,0)
    signal=.25*np.exp(-age/.12)*np.sin(2*np.pi*1000*age)*(t>=.4)*(t<1.)
    fixture=np.column_stack([signal,-.8*signal])+rng.normal(0,.001,(len(t),2))
    path=a.output/'known.wav';sf.write(path,fixture,48000,subtype='FLOAT')
    workspace=EventWorkspace(repo,a.output/'workspace/events');p=workspace.create(dict(upload(path),kind='catch',viewpoint='exterior'))
    master,sr=sf.read(workspace.root/p['id']/'master.wav',always_2d=True,dtype='float32')
    check(np.array_equal(master,fixture.astype(np.float32)),'48 kHz import gain/channel preservation')
    p=workspace.analyze(dict(id=p['id'],kind='catch',name='Known mechanical envelope',seconds=[.4,1.],background_seconds=[0,.3],gated=False))
    check(p['document'] and p['reference_matches_model'],'Material provenance binding')
    check(abs(p['observation']['bands'][1]['decay_seconds']-.12)<.025,'Known amplitude decay')
    value=edit(p);value['controls'].update(seconds=.9,seed=27431);p=workspace.render(value)
    root=workspace.root/p['id'];version=p['last_version'];original=root/version
    actual,_=sf.read(original/'synthesis.wav',dtype='float32');params=p['document']['parameters']
    expected=synth(params,seconds=.9).astype(np.float32);expected=np.pad(expected,(0,len(actual)-len(expected)))
    error=float(np.max(abs(actual.astype(float)-expected)));check(error<2e-7,'Independent reference versus actual C')
    monitor,_=sf.read(original/'preview.wav',dtype='float32');check(np.array_equal(monitor,actual*.25),'Fixed preview gain')
    saved=p['history'][0]['id'];package=json.loads((original/'parameters.json').read_text(encoding='utf-8'))
    # All editable profile numbers are in CSV, and all exported file hashes are checked.
    rows=list(csv.DictReader((original/'parameters.csv').open(encoding='utf-8-sig')))
    count=sum(len(row) for row in params['modes'])+sum(len(row) for row in params['bands'])+6+len(p['controls'])
    check(len(rows)==count,'Complete parameter CSV')
    for row in rows:
        group,index,key=row['group'],row['index'],row['parameter']
        expected_value=p['controls'][key] if group=='audition' else params[key] if group=='profile' else params[group][int(index)][key]
        check(float(row['value'])==expected_value,'CSV number '+str(row))
    manifest=json.loads((original/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():check(sha(original/name)==digest,'Export hash '+name)
    with zipfile.ZipFile(original/'event-design.zip') as archive:check(set(manifest['files'])|{'manifest.json'}==set(archive.namelist()),'ZIP completeness')
    # Compile the generated header with the C contract, then compare every exported scalar.
    compile_dir=a.output/'export_compile';compile_dir.mkdir()
    shutil.copy2(original/'profile.h',compile_dir/'profile.h')
    (compile_dir/'check.c').write_text('''#include "profile.h"
#include <stdio.h>
int main(void){const EsProfile *p=&vsl_authored_event;unsigned k;
 if(!es_profile_valid(p))return 3;
 printf("%u %u %u %.17g %.17g %.17g %.17g %.17g\\n",p->mode_count,p->band_count,p->gated,p->duration_seconds,p->attack_seconds,p->release_seconds,p->sweep_seconds,p->level);
 for(k=0;k<p->mode_count;++k){const EsMode *m=p->modes+k;printf("%.17g %.17g %.17g %.17g %.17g\\n",m->hz,m->amplitude,m->phase,m->decay_seconds,m->end_hz);}
 for(k=0;k<p->band_count;++k){const EsBand *b=p->bands+k;printf("%.17g %.17g %.17g %.17g %.17g\\n",b->hz,b->q,b->amplitude,b->attack_seconds,b->decay_seconds);}
 printf("%.17g %.17g %.17g %.17g %u\\n",vsl_authored_request.strength,vsl_authored_request.pitch,vsl_authored_request.decay,vsl_authored_request.texture,vsl_authored_request.seed);return 0;}
''',encoding='utf-8')
    (compile_dir/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(EventExportCheck LANGUAGES C)\nadd_executable(check check.c "'+(repo/'modules/event_synth/profile.c').as_posix()+'")\ntarget_include_directories(check PRIVATE "'+(repo/'modules').as_posix()+'")\n',encoding='utf-8')
    log=bytearray()
    for command in [ ['cmake','-S',str(compile_dir),'-B',str(compile_dir/'build'),'-G','Visual Studio 17 2022','-A','x64'],
                     ['cmake','--build',str(compile_dir/'build'),'--config','Release'] ]:
        run=subprocess.run(command,capture_output=True,timeout=60,creationflags=0x08000000);log.extend(run.stdout+run.stderr)
        (compile_dir/'compile.log').write_bytes(log);check(run.returncode==0,'Generated C header compilation')
    tokens=subprocess.check_output([str(compile_dir/'build/Release/check.exe')],creationflags=0x08000000).decode().split()
    expected=[len(params['modes']),len(params['bands'])]+[params[k] for k in ('gated','duration_seconds','attack_seconds','release_seconds','sweep_seconds','level')]
    for row in params['modes']:expected.extend(row[k] for k in ('hz','amplitude','phase','decay_seconds','end_hz'))
    for row in params['bands']:expected.extend(row[k] for k in ('hz','q','amplitude','attack_seconds','decay_seconds'))
    expected.extend(p['controls'][k] for k in ('strength','pitch','decay','texture','seed'))
    check(list(map(float,tokens))==expected,'Generated C parameters round trip exactly')
    report['generated_C_header_compiles_and_parameters_exact']=True
    # Import parameter-only preset without source media, regenerate bit-identical PCM.
    imported=workspace.create(dict(package=package));q=workspace.render(edit(imported))
    restored_audio,_=sf.read(workspace.root/q['id']/q['last_version']/'synthesis.wav',dtype='float32')
    check(np.array_equal(restored_audio,actual),'No-source parameter import reproduces PCM')
    # Edit both tone and trigger macro, then restore and re-render the original revision.
    value=edit(p);value['parameters']['modes'][0]['hz']*=1.07;value['controls']['pitch']=.91
    changed=workspace.render(value);changed_audio,_=sf.read(root/changed['last_version']/'synthesis.wav',dtype='float32')
    check(not np.array_equal(changed_audio,actual),'Edits affect actual C output')
    restored=workspace.restore(dict(id=p['id'],revision=saved));again=workspace.render(edit(restored))
    replay,_=sf.read(root/again['last_version']/'synthesis.wav',dtype='float32')
    check(np.array_equal(actual,replay),'History restoration exactly reproduces PCM')
    # Refused re-fit must retain old sound, and must explicitly show stale reference binding.
    old_document=deepcopy(again['document']);refit=workspace.analyze(dict(edit(again),seconds=[0,.12],background_seconds=[.15,.27],gated=False))
    check(refit['analysis']['status']=='analysis_only' and refit['document']==old_document,'Weak event retains prior sound')
    check(refit['reference_matches_model'] is False and refit['preview_stale'],'Refused fit marks reference/parameter mismatch')
    refusals=[refused(lambda:workspace.analyze(dict(id=p['id'],seconds=[0,.3],background_seconds=[.2,.4])),'overlapping intervals'),
        refused(lambda:workspace.view('../outside'),'invalid project identity')]
    invalid=edit(again);invalid['parameters']['level']=float('nan');refusals.append(refused(lambda:workspace.save(invalid),'nonfinite profile'))
    invalid=edit(again);invalid['controls']['seed']=0;refusals.append(refused(lambda:workspace.render(invalid),'invalid seed'))
    invalid=edit(again);invalid['parameters']['modes']*=2;refusals.append(refused(lambda:workspace.render(invalid),'mode capacity'))
    # Gated C path includes user release, pitch sweep, colored noise and zero padding.
    r=Renderer(repo);gated=deepcopy(params);gated.update(gated=1,duration_seconds=3,sweep_seconds=.15)
    for m in gated['modes']:m['end_hz']=min(18000,m['hz']*1.12)
    values=dict(again['controls'],seconds=.8,pitch=1.13,decay=.7,texture=.75,strength=.8,hold_seconds=.3)
    c,gate_report=r.render(gated,'crank',values)
    independent=synth(gated,seed=values['seed'],pitch=values['pitch'],decay=values['decay'],texture=values['texture'],
        strength=values['strength'],seconds=.8,release_at=.3).astype(np.float32)
    independent[round((.3+gated['release_seconds'])*48000):]=0
    gate_error=float(np.max(abs(c.astype(float)-independent)));check(gate_error<2e-7,'Gated sweep/release C comparison')
    check(np.count_nonzero(c[round((.3+gated['release_seconds'])*48000):])==0,'Release leaves no tail beyond voice end')
    # A different input sample rate is explicitly decoded, with native stereo retained.
    other=a.output/'known_44100.wav';tt=np.arange(13230)/44100
    sf.write(other,np.column_stack([.1*np.sin(2*np.pi*300*tt),.1*np.cos(2*np.pi*300*tt)]),44100,subtype='FLOAT')
    converted=workspace.create(dict(upload(other),kind='crank'))
    check(converted['audio']['sample_rate']==48000 and converted['audio']['channels']==2 and converted['audio']['frames']==14400,'Explicit resampling')
    report.update(independent_C_error=error,gated_sweep_release_error=gate_error,known_decay_seconds=p['observation']['bands'][1]['decay_seconds'],
        preserved_48k_stereo=True,explicit_44100_decode=True,source_free_import_pcm_exact=True,history_pcm_exact=True,
        edits_change_PCM=True,analysis_only_preserves_profile=True,stale_reference_visible=True,csv_rows=len(rows),
        export_hashes_verified=True,refusals=refusals,renderer_sha256=r.identity,renderer_sources=r.sources)
    # Real approved A material: re-extract relative to a short immutable contextual crop.
    master=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    x,rate=sf.read(master,start=35*48000,stop=round(38.2*48000),always_2d=True)
    real=a.output/'A_start_context.wav';sf.write(real,x,rate,subtype='FLOAT')
    ap=workspace.create(dict(upload(real),kind='catch',viewpoint='cabin'))
    ap=workspace.analyze(dict(id=ap['id'],name='A 接火混合声学候选',seconds=[2.22,3.02],background_seconds=[0,1.2],gated=False,
        context='Approved A 35.0–38.2 s crop. Candidate event at original 37.22–38.02 s; not physically isolated ignition.'))
    ap=workspace.render(edit(ap));real_output=workspace.root/ap['id']/ap['last_version']
    shutil.copytree(real_output,a.output/'A_catch_export')
    report['approved_A']=dict(project=ap['id'],source_sha256=sha(master),crop_original_seconds=[35,38.2],
        event_original_seconds=[37.22,38.02],contrast_db=ap['observation']['event_to_background_db'],
        hearing_accepted=False,physical_separation=False,output=str(real_output))
    # Test-only local server owns a bounded lifetime and never launches the live controller.
    if a.ui:
        server=create_server(repo,a.output/'web_workspace',0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_address[1]);report['test_server']=url
        node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
        deps=node.parents[1]/'node_modules';ui=a.output/'ui';ui.mkdir()
        shutil.copy2(repo/'tools/verify_event_designer_ui.cjs',ui/'executed_verification.cjs')
        try:
            command=[str(node),str(repo/'tools/verify_event_designer_ui.cjs'),str(deps),str(ui),str(path),url]
            result=subprocess.run(command,cwd=repo,capture_output=True,timeout=180,creationflags=0x08000000)
            (a.output/'ui-stdout.log').write_bytes(result.stdout);(a.output/'ui-stderr.log').write_bytes(result.stderr)
            check(result.returncode==0,'Browser workflow: '+result.stderr.decode('utf-8',errors='replace'))
            report['ui']=json.loads((ui/'report.json').read_text(encoding='utf-8'))
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
        check(not thread.is_alive(),'Test server stops')
        report['test_server_closed']=True
    report['result']='passed'
    (a.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1]);out.mkdir(exist_ok=True,parents=True)
            (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
