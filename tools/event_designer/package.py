"""Editable JSON/C/CSV exports and their renderer/provenance identities."""
import csv
import json
from pathlib import Path
import zipfile
from event_authoring.audio import sha
from event_authoring.export import c_profile,number
from event_authoring.model import KINDS
from event_authoring.material_reviews import rejection


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8',newline='\n')


def export(folder,document,controls,report,source_context=None,candidate_scan=None):
    value=dict(schema='vsl.event-design/1',document=document,controls=controls,render_report=report,
        status='editable candidate; listening acceptance is separate',runtime='pure synthesis; preview WAV is not a runtime asset')
    review=rejection(document)
    if review:
        value['material_review']=review
        value['status']='historical experiment; source rejected as afterfire reference by user'
    if source_context is not None:
        value['source_context']=source_context
        write_json(folder/'source-context.json',source_context)
    if candidate_scan is not None:
        value['candidate_scan']=candidate_scan
        write_json(folder/'candidate-scan.json',candidate_scan)
    write_json(folder/'parameters.json',value)
    text='/* Editable event profile. Provenance and preview macros: parameters.json. No PCM. */\n'
    if review:text+='/* Historical experiment: source rejected as afterfire reference by user. */\n'
    text+='#include "event_synth/api.h"\nstatic const EsProfile vsl_authored_event='+c_profile(document['parameters'])+';\n'
    text+='static const EsRequest vsl_authored_request={1,0,'+str(KINDS.index(document['kind']))+',100,'+str(controls['seed'])+','
    text+=','.join(number(controls[k]) for k in ('strength','pitch','decay','texture'))+'};\n'
    text+='/* Gated audition release frame: '+str(report['release_frame'])+'; production release comes from event_control. */\n'
    (folder/'profile.h').write_text(text,encoding='utf-8',newline='\n')
    with (folder/'parameters.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['group','index','parameter','value'])
        for key,v in document['parameters'].items():
            if key in ('modes','bands'):
                for i,row in enumerate(v):
                    for k,item in row.items():writer.writerow([key,i,k,item])
            elif key=='contours':
                for i,c in enumerate(v):
                    for field in ('low_hz','high_hz'):writer.writerow(['contours',i,field,c[field]])
                    for j,(time,gain) in enumerate(zip(c['seconds'],c['gain'])):
                        writer.writerow(['contour_'+str(i),j,'seconds',time]);writer.writerow(['contour_'+str(i),j,'gain',gain])
            else:writer.writerow(['profile','',key,v])
        for key,v in controls.items():writer.writerow(['audition','',key,v])
    manifest={path.name:sha(path) for path in folder.iterdir() if path.is_file()}
    write_json(folder/'manifest.json',dict(schema='vsl.event-design-manifest/1',files=manifest))
    with zipfile.ZipFile(folder/'event-design.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            if path.is_file() and path.suffix!='.zip':archive.write(path,path.name)
