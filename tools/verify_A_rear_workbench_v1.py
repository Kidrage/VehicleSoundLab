"""Actual job9 extraction, editing/history and source-free C parameter exports."""
import argparse
import csv
from pathlib import Path
import shutil
import subprocess
import threading

import numpy as np
import soundfile as sf

from event_designer.workspace import EventWorkspace
from research_archive_v1 import load, save, sha
from sound_designer.server import create_server


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    data=Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    candidate=load(args.profile)
    save(args.output/'fixture.json',dict(context=str(data/'selection1/context-original.wav'),
                                       expected=candidate['parameters']))
    script=(repo/'tools/verify_event_joint_web_v1.cjs').read_text(encoding='utf-8')
    for old,new,count in [
        ('headless:true','headless:true,args:["--mute-audio"]',1),
        ("'#kind','crank'","'#kind','catch'",1),
        ("'#viewpoint','cabin'","'#viewpoint','exterior'",1),
        ("start:'3.2',end:'3.95',bgStart:'.2',bgEnd:'1.2'","start:'1.18',end:'2.38',bgStart:'0',bgEnd:'.25'",1),
        ('band-contour-v2','band-contour-v5',4),
        ("await page.check('#fitGated')","await page.uncheck('#fitGated')",1),
        ("querySelectorAll('#contourRows fieldset').length===1","querySelectorAll('#contourRows fieldset').length===4",1),
        ("p.document.fit.contour_fit.bands[0].selected===false","p.document.fit.contour_fit.bands.every(r=>r.selected)",1),
        ("includes('保留原包络')","includes('提取多段包络')",1),
        ('weak_band_explicitly_retained:true','four_reliable_bands_visible:true',1)]:
        assert script.count(old)==count,(old,script.count(old))
        script=script.replace(old,new)
    executed=args.output/'executed_browser.cjs'
    executed.write_text(script,encoding='utf-8')
    shutil.copy2(__file__,args.output/'executed_verification.py')
    node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    server=create_server(repo,args.output/'server-root',0)
    thread=threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result=subprocess.run([str(node),str(executed),str(node.parents[1]/'node_modules'),
            str(args.output),str(args.output/'fixture.json'),'http://127.0.0.1:'+str(server.server_address[1])],
            capture_output=True,timeout=300,creationflags=0x08000000)
        (args.output/'stdout.log').write_bytes(result.stdout)
        (args.output/'stderr.log').write_bytes(result.stderr)
        assert result.returncode==0,result.stderr.decode(errors='replace')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    assert not thread.is_alive()
    browser=load(args.output/'report.json')
    workspace=EventWorkspace(repo,args.output/'server-root/events')
    project=workspace.view(browser['project_id'])
    assert project['envelope_fit']=='band-contour-v5'
    assert project['document']['source_job']['schema']=='vsl.event-authoring-job/9'
    version=workspace.root/project['id']/project['last_version']
    rows=list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
    controls=sum(len(c['seconds']) for c in candidate['parameters']['contours'])
    assert sum(r['group'].startswith('contour_') for r in rows)==controls*2
    assert sum(r['group']=='contours' for r in rows)==8
    header=args.output/'header';header.mkdir()
    shutil.copy2(version/'profile.h',header/'profile.h')
    previous=Path('E:/VehicleSoundLab/references/analysis/event_joint_v1/web1/header')
    for name in ('check.c','CMakeLists.txt'):shutil.copy2(previous/name,header/name)
    for cmd in (['cmake','-S',str(header),'-B',str(header/'build'),'-G','Visual Studio 17 2022','-A','x64'],
                ['cmake','--build',str(header/'build'),'--config','Release']):
        built=subprocess.run(cmd,capture_output=True,creationflags=0x08000000)
        assert built.returncode==0,built.stderr.decode(errors='replace')
    actual=list(map(float,subprocess.check_output([str(header/'build/Release/check.exe')],creationflags=0x08000000).split()))
    wanted=[]
    for contour in candidate['parameters']['contours']:
        wanted.extend([contour['low_hz'],contour['high_hz']])
        wanted.extend(value for pair in zip(contour['seconds'],contour['gain']) for value in pair)
    assert actual==wanted
    real=EventWorkspace(repo,Path('E:/VehicleSoundLab/designs/events'))
    imported=real.create(dict(package=dict(schema='vsl.event-design/1',document=project['document'],controls=project['controls'])))
    imported=real.render(dict(id=imported['id']))
    final=real.root/imported['id']/imported['last_version']/'synthesis.wav'
    a,_=sf.read(final,dtype='float32');b,_=sf.read(version/'synthesis.wav',dtype='float32')
    assert np.array_equal(a,b)
    binding=load(data/'selection1/runtime.json')
    assert len(binding)==459 and all(sha(repo/name)==digest for name,digest in binding.items())
    save(args.output/'verification.json',dict(result='passed',browser=browser,
        actual_job9_extraction_parameters_exact=True,CSV_and_C_header_exact=True,
        source_free_import_C_PCM_exact=True,actual_editable_project=imported['id'],
        actual_parameters=str(final.with_name('parameters.json')),own_server_closed=True,
        runtime_voice_files_unchanged=459,timbre_accepted=False))
    print(dict(result='passed',project=imported['id']),flush=True)


if __name__=='__main__':main()
