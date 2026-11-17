"""Actual adaptive fit in the workbench, editable history and C/CSV exports."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
import threading
import numpy as np
import soundfile as sf
from event_authoring.audio import read
from event_designer.workspace import EventWorkspace
from sound_designer.server import create_server
from research_archive_v1 import load,save


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    root=Path('E:/VehicleSoundLab/references/analysis/event_knots_v1')
    x,rate,provenance=read(Path('E:/VehicleSoundLab/references/clean/B_decoded_float.wav'),12.,20.)
    sf.write(out/'context.wav',x,rate,subtype='FLOAT')
    candidate=load(root/'verification1/B/analysis/profile.json')['parameters']
    save(out/'fixture.json',dict(context=str(out/'context.wav'),expected=candidate))
    script=(repo/'tools/verify_event_joint_web_v1.cjs').read_text(encoding='utf-8')
    assert script.count('band-contour-v2')>=3;script=script.replace('band-contour-v2','band-contour-v3')
    before="const original=p.document.parameters.contours[0].gain[1];"
    assert before in script
    script=script.replace(before,"assert((await page.textContent('#analysisInfo')).includes('已按素材首响选择控制点位置'));"+
        "const shown=await page.locator('#contourRows tbody tr').evaluateAll(rows=>rows.flatMap(tr=>Array.from(tr.querySelectorAll('input'),x=>({value:Number(x.value),title:x.title,label:x.parentElement.querySelector('[data-readout]').textContent}))));"+
        "assert(shown.some(x=>x.label.includes('e-')));for(const x of shown){assert.equal(Number(x.title),x.value);assert(Math.abs(Number(x.label)-x.value)<=Math.max(1e-30,Math.abs(x.value)*1e-5));}"+before)
    executed=out/'executed_browser.cjs';executed.write_text(script,encoding='utf-8')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=create_server(repo,out/'server-root',0);thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        run=subprocess.run([str(node),str(executed),str(node.parents[1]/'node_modules'),str(out),str(out/'fixture.json'),
            'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,timeout=300,creationflags=0x08000000)
        (out/'stdout.log').write_bytes(run.stdout);(out/'stderr.log').write_bytes(run.stderr)
        assert run.returncode==0,run.stderr.decode(errors='replace')
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive();browser=load(out/'report.json');workspace=EventWorkspace(repo,out/'server-root/events')
    p=workspace.view(browser['project_id']);version=workspace.root/p['id']/p['last_version']
    rows=list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
    assert sum(r['group'].startswith('contour_') for r in rows)==16 and sum(r['group']=='contours' for r in rows)==2
    header=out/'header';header.mkdir();shutil.copy2(version/'profile.h',header/'profile.h')
    prior=Path('E:/VehicleSoundLab/references/analysis/event_joint_v1/web1/header')
    for name in ('check.c','CMakeLists.txt'):shutil.copy2(prior/name,header/name)
    for cmd in (['cmake','-S',str(header),'-B',str(header/'build'),'-G','Visual Studio 17 2022','-A','x64'],
                ['cmake','--build',str(header/'build'),'--config','Release']):
        completed=subprocess.run(cmd,capture_output=True,creationflags=0x08000000);assert completed.returncode==0,completed.stderr.decode(errors='replace')
    values=list(map(float,subprocess.check_output([str(header/'build/Release/check.exe')],creationflags=0x08000000).split()))
    expected=[]
    for c in candidate['contours']:
        expected.extend([c['low_hz'],c['high_hz']]);expected.extend(v for pair in zip(c['seconds'],c['gain']) for v in pair)
    assert values==expected
    actual=EventWorkspace(repo,Path('E:/VehicleSoundLab/designs/events'))
    imported=actual.create(dict(package=dict(schema='vsl.event-design/1',document=p['document'],controls=p['controls'])))
    imported=actual.render(dict(id=imported['id']));file=actual.root/imported['id']/imported['last_version']/'synthesis.wav'
    a,_=sf.read(file,dtype='float32');b,_=sf.read(version/'synthesis.wav',dtype='float32');assert np.array_equal(a,b)
    save(out/'verification.json',dict(result='passed',browser=browser,header_knots_exact=True,csv_knots_present=True,
        original_source=provenance,own_server_closed=True,source_free_import_C_PCM_exact=True,
        actual_editable_project=imported['id'],actual_parameters=str(file.with_name('parameters.json')),timbre_accepted=False))
    shutil.copy2(__file__,out/'executed_verification.py');print(dict(result='passed',project=imported['id']),flush=True)


if __name__=='__main__':main()
