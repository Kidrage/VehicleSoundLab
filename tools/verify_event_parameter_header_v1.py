"""Compile an exported event header and read every profile/request number back."""
import argparse
from pathlib import Path
import shutil
import subprocess
from event_authoring.model import KINDS
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];package=load(args.package/'parameters.json')
    p=package['document']['parameters'];controls=package['controls'];fields=[]
    def field(expression,value):fields.append((expression,float(value)))
    for key,value in [('mode_count',len(p['modes'])),('band_count',len(p['bands'])),('gated',p['gated'])]:field('vsl_authored_event.'+key,value)
    for key in ('duration_seconds','attack_seconds','release_seconds','sweep_seconds','level','noise_lowpass_hz'):
        field('vsl_authored_event.'+key,p.get(key,0))
    for group,keys in [('modes',('hz','amplitude','phase','decay_seconds','end_hz','attack_seconds')),
                       ('bands',('hz','q','amplitude','attack_seconds','decay_seconds'))]:
        for index,row in enumerate(p[group]):
            for key in keys:field(f'vsl_authored_event.{group}[{index}].{key}',row.get(key,0))
    for index in range(4):
        contour=p.get('contours',[])[index] if index<len(p.get('contours',[])) else None
        prefix=f'vsl_authored_event.contours[{index}]'
        field(prefix+'.count',len(contour['seconds']) if contour else 0)
        for key in ('low_hz','high_hz'):field(prefix+'.'+key,contour[key] if contour else 0)
        for key in ('seconds','gain'):
            for knot in range(8):field(prefix+f'.{key}[{knot}]',contour[key][knot] if contour and knot<len(contour[key]) else 0)
    for key,value in [('id',1),('requested_frame',0),('type',KINDS.index(package['document']['kind'])),
                       ('priority',100),('seed',controls['seed'])]:field('vsl_authored_request.'+key,value)
    for key in ('strength','pitch','decay','texture'):field('vsl_authored_request.'+key,controls[key])
    shutil.copy2(args.package/'profile.h',args.output/'profile.h');shutil.copy2(__file__,args.output/'executed_verification.py')
    source='#include "profile.h"\n#include <stdio.h>\nint main(void){if(!es_profile_valid(&vsl_authored_event))return 3;\n'
    source+=''.join('printf("%.17g\\n",(double)('+expression+'));\n' for expression,_ in fields)+'return 0;}\n'
    (args.output/'check.c').write_text(source,encoding='utf-8')
    (args.output/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(EventHeader LANGUAGES C)\n'+
        'add_executable(check check.c "'+(repo/'modules/event_synth/profile.c').as_posix()+'")\n'+
        'target_include_directories(check PRIVATE "'+(repo/'modules').as_posix()+'")\n',encoding='utf-8')
    cmake=shutil.which('cmake');assert cmake
    for name,command in [('configure',[cmake,'-S',str(args.output),'-B',str(args.output/'build'),'-G','Visual Studio 17 2022','-A','x64']),
                         ('build',[cmake,'--build',str(args.output/'build'),'--config','Release'])]:
        run=subprocess.run(command,capture_output=True,timeout=120,creationflags=0x08000000)
        (args.output/(name+'.log')).write_bytes(run.stdout+run.stderr);assert run.returncode==0
    actual=subprocess.check_output([str(args.output/'build/Release/check.exe')],creationflags=0x08000000,text=True)
    (args.output/'readback.txt').write_text(actual,encoding='utf-8');numbers=list(map(float,actual.split()))
    assert numbers==[value for _,value in fields]
    save(args.output/'expected-fields.json',dict(fields))
    report=dict(result='passed',all_compiled_numeric_fields_exact=True,fields=len(fields),
        exported_header_sha256=sha(args.package/'profile.h'),package_sha256=sha(args.package/'parameters.json'),goal_complete=False)
    save(args.output/'report.json',report);print(report,flush=True)


if __name__=='__main__':main()
