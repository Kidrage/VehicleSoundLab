"""Verify material response-fit UI, preservation/refusal and compiled C parameter exports."""
import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile
from unittest.mock import patch

from event_authoring.audio import sha
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json
from sound_designer.server import create_server
from startup_timbre_v1.projects import edit


def compile_header(repo,version,output):
    output.mkdir();shutil.copy2(version/'profile.h',output/'profile.h')
    (output/'check.c').write_text('''#include "profile.h"
#include <stdio.h>
int main(void){const EsProfile *p=&vsl_authored_event;unsigned k;
 if(!es_profile_valid(p))return 3;
 printf("%u %u %u %.17g %.17g %.17g %.17g %.17g %.17g\\n",p->mode_count,p->band_count,p->gated,p->duration_seconds,p->attack_seconds,p->release_seconds,p->sweep_seconds,p->level,p->noise_lowpass_hz);
 for(k=0;k<p->mode_count;++k){const EsMode *m=p->modes+k;printf("%.17g %.17g %.17g %.17g %.17g\\n",m->hz,m->amplitude,m->phase,m->decay_seconds,m->end_hz);}
 for(k=0;k<p->band_count;++k){const EsBand *b=p->bands+k;printf("%.17g %.17g %.17g %.17g %.17g\\n",b->hz,b->q,b->amplitude,b->attack_seconds,b->decay_seconds);}
 return 0;}
''',encoding='utf-8')
    (output/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(EventColorExport LANGUAGES C)\nadd_executable(check check.c "'+
        (repo/'modules/event_synth/profile.c').as_posix()+'")\ntarget_include_directories(check PRIVATE "'+(repo/'modules').as_posix()+'")\n',encoding='utf-8')
    log=bytearray()
    for command in [['cmake','-S',str(output),'-B',str(output/'build'),'-G','Visual Studio 17 2022','-A','x64'],
                    ['cmake','--build',str(output/'build'),'--config','Release']]:
        run=subprocess.run(command,capture_output=True,timeout=60,creationflags=0x08000000);log.extend(run.stdout+run.stderr)
        (output/'compile.log').write_bytes(log);assert run.returncode==0
    actual=list(map(float,subprocess.check_output([str(output/'build/Release/check.exe')],creationflags=0x08000000).split()))
    p=json.loads((version/'parameters.json').read_text(encoding='utf-8'))['document']['parameters']
    expected=[len(p['modes']),len(p['bands'])]+[p[k] for k in ('gated','duration_seconds','attack_seconds','release_seconds','sweep_seconds','level','noise_lowpass_hz')]
    for row in p['modes']:expected.extend(row[k] for k in ('hz','amplitude','phase','decay_seconds','end_hz'))
    for row in p['bands']:expected.extend(row[k] for k in ('hz','q','amplitude','attack_seconds','decay_seconds'))
    assert actual==expected


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--delivery',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];projects=json.loads((a.delivery/'projects/report.json').read_text(encoding='utf-8'))
    catch=next(row for row in projects['projects'] if row['kind']=='catch')
    fixture=a.output/'fixture.json';write_json(fixture,dict(context=projects['context'],expected=catch['document']['parameters']))
    server=create_server(repo,a.output/'workspace',0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    ui=a.output/'ui';ui.mkdir();script=repo/'tools/verify_event_response_ui_v1.cjs';shutil.copy2(script,ui/script.name)
    try:
        run=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(ui),str(fixture),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=240,creationflags=0x08000000)
        (ui/'stdout.log').write_bytes(run.stdout);(ui/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=json.loads((ui/'report.json').read_text(encoding='utf-8'));workspace=EventWorkspace(repo,a.output/'workspace/events')
    project=workspace.view(browser['project_id']);folder=workspace.root/project['id'];version=folder/project['last_version']
    compile_header(repo,version,a.output/'export-compile')
    rows=list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
    assert any(r['parameter']=='noise_lowpass_hz' and float(r['value'])==10000 for r in rows)
    manifest=json.loads((version/'manifest.json').read_text(encoding='utf-8'))
    assert all(sha(version/name)==digest for name,digest in manifest['files'].items())
    with zipfile.ZipFile(version/'event-design.zip') as archive:assert set(archive.namelist())==set(manifest['files'])|{'manifest.json'}
    # A failed response fit must preserve the current editable sound and previews.
    prior=deepcopy(project['document']);parameters=prior['parameters']
    with patch('event_authoring.response_fit.search',return_value=(parameters,dict(qualified=False,reason='injected infeasible response'))):
        rejected=workspace.analyze(dict(edit(project),seconds=[2.22,3.02],background_seconds=[0,1.2],gated=False))
    assert rejected['analysis']['refusal_kind']=='response_fit' and rejected['document']==prior
    assert (folder/rejected['analysis_run']/'refused-fit.json').is_file()
    assert (folder/project['last_version']/'synthesis.wav').is_file()
    # Malformed or scoped jobs must not silently opt into the new full-band law.
    from author_event import author
    invalid=[]
    for schema,scope in [('vsl.event-authoring-job/1',dict(mode='full')),('vsl.event-authoring-job/3',dict(mode='band',low_hz=1200,high_hz=14000))]:
        job=dict(schema=schema,kind='catch',name='invalid',source=projects['context'],seconds=[2.22,3.02],background_seconds=[0,1.2],
                 response_fit='source-response-v1',analysis_scope=scope)
        file=a.output/('invalid'+str(len(invalid))+'.json');write_json(file,job)
        try:author(file,a.output/('invalid-output'+str(len(invalid))))
        except ValueError:invalid.append(schema+' / '+scope['mode'])
        else:raise AssertionError('Invalid response fit contract admitted')
    shutil.copy2(__file__,a.output/'executed_verification.py')
    write_json(a.output/'report.json',dict(schema='vsl.event-response-workbench/1',result='passed',ui=browser,
        owned_server_closed=True,compiled_C_header_all_fields_exact=True,CSV_ZIP_manifest_verified=True,
        infeasible_response_preserves_model_and_refused_fit=True,invalid_protocols_refused=invalid,
        timbre_accepted=False,goal_complete=False))
    print(json.dumps(dict(result='passed',project=browser['project_id'])))


if __name__=='__main__':
    try:main()
    except Exception:
        import sys,traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
