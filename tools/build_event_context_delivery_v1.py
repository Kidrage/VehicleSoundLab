"""Keep approved-source exclusions and editable diagnostic projects; no new event bank."""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import soundfile as sf
from event_authoring.audio import read,sha
from event_designer.workspace import EventWorkspace
from event_designer.package import write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    manifest=json.loads((repo/'references/segments_v1.json').read_text(encoding='utf-8'))
    approvals=json.loads((data/'references/approval_manifest.json').read_text(encoding='utf-8'))
    workspace=EventWorkspace(repo,data/'designs/events');rows=[]
    specs=[dict(name='E18.59 · 补油段排除记录',source='E',context=[17.8,19.4],event=[18.565,18.665],
                before=[18.24,18.44],after=[18.75,18.95],fit=True,
                note='持续补油段中的声学增量；未证明孤立回火，全频拟合低频未通过。保留排除证据，不接入正式事件库。'),
           dict(name='B122.53 · 操作声排除参考',source='B',context=[121.53,124.03],event=[122.505,122.605],
                before=[122.18,122.38],after=[122.69,122.89],fit=False,
                note='画面中可见手部接触仪表台附近；只作操作声干扰参考，未确认回火，不拟合。'),
           dict(name='B526.055 · 行驶短声待辨识',source='B',context=[525.055,527.555],event=[526.03,526.13],
                before=[525.705,525.905],after=[526.215,526.415],fit=False,
                note='驾驶转弯上下文，画面未观察到明确换挡；保持未分类，不拟合成回火。'),
           dict(name='B546.135 · 行驶短声待辨识',source='B',context=[545.135,547.635],event=[546.11,546.21],
                before=[545.785,545.985],after=[546.295,546.495],fit=False,
                note='驾驶转弯上下文，画面未观察到明确换挡；保持未分类，不拟合成回火。')]
    for index,spec in enumerate(specs):
        identity=spec['source'];assert any(r['id']==identity and r['approved'] for r in approvals)
        source=data/manifest['sources'][identity]['master'];assert sha(source)==manifest['sources'][identity]['master_sha256']
        audio,rate,origin=read(source,*spec['context'])
        clip=a.output/(identity+'_'+str(index)+'_original.wav');sf.write(clip,audio,rate,subtype='FLOAT')
        p=workspace.create(dict(filename=clip.name,audio=base64.b64encode(clip.read_bytes()).decode(),kind='afterfire',
                                viewpoint='exterior' if identity=='E' else 'cabin'))
        shift=lambda pair:[(round(t*48000)-origin['first_frame'])/48000 for t in pair]
        edit=dict(id=p['id'],name=spec['name'],context=spec['note']+' afterfire仅为工程槽，无已确认物理身份。',
                  seconds=shift(spec['event']),background_seconds=shift(spec['before']),following_background_seconds=shift(spec['after']),
                  analysis_scope=dict(mode='full'),response_fit='source-response-v1')
        p=workspace.probe_context(edit)
        if spec['fit']:
            p=workspace.analyze(dict(edit,gated=False))
            assert p['analysis']['refusal_kind']=='response_fit' and p['document'] is None
            failed=json.loads((workspace.root/p['id']/p['analysis_run']/'report.json').read_text(encoding='utf-8'))
            previous=json.loads((data/'references/analysis/exhaust_full_v1/fit1/report.json').read_text(encoding='utf-8'))
            assert failed['fit']['source_response_fit']==previous['fit']['source_response_fit']
        assert p['document'] is None and p['context_matches_selection'] and p['preview_url'] is None
        folder=workspace.root/p['id'];target=a.output/('project_'+str(index));shutil.copytree(folder,target)
        rows.append(dict(name=spec['name'],project_id=p['id'],project_folder=str(folder),source=origin,specification=spec,
                         context_probe=deepcopy(p['context_probe']),analysis=p.get('analysis'),parameters_available=False,
                         physical_identity_confirmed=False,formal_profile_promoted=False))
    report=dict(schema='vsl.event-context-delivery/1',projects=rows,
                scan_report=str(data/'references/analysis/approved_event_scan_v1/B_middle1/report.json'),
                conclusion='No new confirmed physical afterfire; preserve E full-band refusal and B handling/driving confounds.',
                existing_C_and_global_bank_changed=False,new_download=False,goal_complete=False)
    write_json(a.output/'report.json',report);shutil.copy2(__file__,a.output/'executed_builder.py')
    print(json.dumps(dict(output=str(a.output),projects=[r['project_id'] for r in rows]),ensure_ascii=False))


if __name__=='__main__':main()
