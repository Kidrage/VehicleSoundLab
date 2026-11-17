"""Material fit, browser editing/history and C/CSV parameter export."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import threading
import numpy as np
import soundfile as sf
from event_authoring.audio import read
from event_designer.package import write_json
from event_designer.workspace import EventWorkspace
from sound_designer.server import create_server


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/startup_contour_v1')
    source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    x,rate,provenance=read(source,35.,40.5);sf.write(out/'context.wav',x,rate,subtype='FLOAT')
    candidate=json.loads((root/'candidate1/analysis/profile.json').read_text(encoding='utf-8'))
    write_json(out/'fixture.json',dict(context=str(out/'context.wav'),expected=candidate['parameters']))
    server=create_server(repo,out/'server-root',0);thread=threading.Thread(target=server.serve_forever);thread.start()
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    script=repo/'tools/verify_startup_contour_web_v1.cjs';shutil.copy2(script,out/script.name)
    try:
        run=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(out),str(out/'fixture.json'),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=240,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(run.stdout);(out/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=json.loads((out/'report.json').read_text(encoding='utf-8'));workspace=EventWorkspace(repo,out/'server-root/events')
    p=workspace.view(browser['project_id']);version=workspace.root/p['id']/p['last_version']
    rows=list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
    assert sum(r['group'].startswith('contour_') for r in rows)==32,rows
    assert sum(r['group']=='contours' for r in rows)==4
    folder=out/'header';folder.mkdir();shutil.copy2(version/'profile.h',folder/'profile.h')
    (folder/'check.c').write_text('#include "profile.h"\n#include <stdio.h>\nint main(void){unsigned i,j;for(i=0;i<ES_CONTOURS;++i){const EsContour *c=vsl_authored_event.contours+i;if(c->count){printf("%.17g %.17g\\n",c->low_hz,c->high_hz);for(j=0;j<c->count;++j)printf("%.17g %.17g\\n",c->seconds[j],c->gain[j]);}}return 0;}\n',encoding='utf-8')
    (folder/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(exported C)\nadd_executable(check check.c)\ntarget_include_directories(check PRIVATE "'+(repo/'modules').as_posix()+'")\n',encoding='utf-8')
    for cmd in (['cmake','-S',str(folder),'-B',str(folder/'build'),'-G','Visual Studio 17 2022','-A','x64'],['cmake','--build',str(folder/'build'),'--config','Release']):
        done=subprocess.run(cmd,capture_output=True,creationflags=0x08000000);assert done.returncode==0,done.stderr.decode(errors='replace')
    values=list(map(float,subprocess.check_output([str(folder/'build/Release/check.exe')],creationflags=0x08000000).split()))
    expected=[]
    for c in p['document']['parameters']['contours']:
        expected.extend([c['low_hz'],c['high_hz']]);expected.extend(v for pair in zip(c['seconds'],c['gain']) for v in pair)
    assert values==expected,(values,expected)
    # Save a new editable project without changing an existing candidate.
    actual=EventWorkspace(repo,Path('E:/VehicleSoundLab/designs/events'))
    loaded=actual.create(dict(package=dict(document=p['document'],schema='vsl.event-design/1',controls=p['controls'])))
    loaded=actual.render(dict(id=loaded['id']));actualfile=actual.root/loaded['id']/loaded['last_version']/'synthesis.wav'
    a,_=sf.read(actualfile,dtype='float32');b,_=sf.read(version/'synthesis.wav',dtype='float32');assert np.array_equal(a,b)
    write_json(out/'verification.json',dict(result='passed',browser=browser,header_contours_exact=True,
        csv_contours_present=True,original_source=provenance,own_server_closed=True,
        actual_editable_project=loaded['id'],actual_parameters=str(actualfile.with_name('parameters.json')),
        source_free_import_C_PCM_exact=True,timbre_accepted=False))
    print(json.dumps(dict(result='passed',project=loaded['id'])),flush=True)


if __name__=='__main__':main()
