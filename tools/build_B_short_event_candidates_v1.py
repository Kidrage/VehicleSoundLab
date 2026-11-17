"""Fixed top-six B short events: original contexts and diagnostic parameter fits."""
import argparse
import base64
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_designer.workspace import EventWorkspace
from event_authoring.audio import read
from event_authoring.model import synth
from event_authoring.native import Renderer,controls
from event_authoring.measure import spectrum
from event_authoring.response_fit import EDGES
from event_review import page
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    root=data/'references/analysis/short_event_scan_v1'
    scan=load(root/'B-scan1/report.json');context=load(root/'B-contexts1/report.json')
    selected=sorted((r for r in scan['candidates'] if r['both_full_band_above_3db']),
                    key=lambda r:(-r['minimum_contrast_db'],r['source_seconds']))[:6]
    assert [r['source_seconds'] for r in selected]==[521.863,522.097,521.891,142.437,785.754,522.310]
    master=Path(scan['source']);assert sha(master)==scan['source_sha256']
    workspace=EventWorkspace(repo,out/'projects');native=Renderer(repo);rows=[];tracks=[]
    review=out/'review';review.mkdir()
    for path in [Path(__file__),repo/'research/short_event_scan_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py')),
                 *sorted((repo/'tools/event_designer').glob('*.py'))]:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    report=dict(result='running',goal_complete=False,timbre_accepted=False,physical_afterfire_confirmed=False)
    try:
        for number,(event,case) in enumerate(zip(selected,context['cases']),1):
            name='B_short_'+str(number);folder=root/'B-contexts1'/name
            assert case['name']==name and case['source']['sha256']==scan['source_sha256']
            seconds=case['specification']['seconds'];assert seconds==[event['source_seconds']-1,event['source_seconds']+1]
            original=folder/'original.wav';samples,rate=sf.read(original,always_2d=True)
            expected,_,_=read(master,*seconds);assert np.array_equal(samples,expected)
            p=workspace.create(dict(filename=name+'.wav',audio=base64.b64encode(original.read_bytes()).decode(),
                kind='afterfire',viewpoint='cabin'))
            offset=round(seconds[0]*48000)
            local=lambda pair:[(round(v*48000)-offset)/48000 for v in pair]
            args=dict(id=p['id'],seconds=local(event['event_seconds']),background_seconds=local(event['before_seconds']),
                following_background_seconds=local(event['after_seconds']),
                context='B original '+str(event['source_seconds'])+'s; unclassified acoustic event, NOT confirmed afterfire; diagnostic only.')
            p=workspace.probe_context(args)
            p=workspace.analyze(dict(args,response_fit='source-response-v1'))
            row=dict(rank=number,source_seconds=event['source_seconds'],minimum_contrast_db=event['minimum_contrast_db'],
                     project=p['id'],status=p['analysis'].get('status','profile_compiled'),
                     event_seconds=event['event_seconds'],before_seconds=event['before_seconds'],after_seconds=event['after_seconds'],
                     physical_identity_confirmed=False,global_bank_changed=False)
            stem='B-'+str(number)
            sf.write(review/(stem+'-original.wav'),samples*.25,rate,subtype='FLOAT')
            shutil.copy2(folder/'timeline.png',review/(stem+'-timeline.png'))
            shutil.copy2(folder/'dashboard.jpg',review/(stem+'-frames.jpg'))
            tracks.append(dict(label=f'{number} · B {event["source_seconds"]:.3f}s 原声上下文',file=stem+'-original.wav',
                description='原始双声道，固定四分之一监听增益；事件在约1秒处；未确认物理动作。'))
            if p['document']:
                p=workspace.render(dict(id=p['id']));version=workspace.root/p['id']/p['last_version']
                document=p['document'];profile=document['parameters']
                recorded,_,_=read(master,*event['event_seconds']);bg,_,_=read(master,*event['before_seconds'])
                f,power=spectrum(recorded);fb,bp=spectrum(bg);positive=np.maximum(0,power-np.interp(f,fb,bp))
                targets=np.array([positive[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]) for lo,hi in EDGES]);total=targets.sum()
                trials=[]
                for seed in (27431,1049,17467,28123):
                    actual,_=native.render(profile,p['kind'],controls(dict(seed=seed,seconds=.2)))
                    expected=synth(profile,seed=seed);assert np.max(abs(actual[:len(expected)]-expected))<2e-6
                    hz,sp=spectrum(actual[:len(expected),None]);bands=[]
                    for (lo,hi),target in zip(EDGES,targets):
                        generated=float(sp[(hz>=lo)&(hz<hi)].sum()*(hz[1]-hz[0]))
                        db=float(10*np.log10(max(generated,1e-30)/max(target,1e-30)))
                        passed=abs(db)<=3 if target>=total*1e-4 else generated<=max(target*2,total*2e-4)
                        bands.append(dict(hz=[lo,hi],error_db=db,passed=bool(passed)))
                    trials.append(dict(seed=seed,bands=bands,qualified=all(b['passed'] for b in bands)))
                row.update(C_seeds=trials,multi_seed_qualified=all(t['qualified'] for t in trials),
                           renderer_sha256=p['render_report']['renderer_sha256'])
                # Pad/space identical pure-C single events for convenient audition; no recording loop.
                actual,_=sf.read(version/'synthesis.wav',always_2d=False)
                audition=np.zeros(2*rate)
                for at in (.25,.8,1.35):audition[round(at*rate):round(at*rate)+len(actual)]+=actual
                sf.write(review/(stem+'-C.wav'),audition*.25,rate,subtype='FLOAT')
                shutil.copy2(version/'event-design.zip',review/(stem+'-parameters.zip'))
                tracks.append(dict(label=f'{number} · C短声诊断',file=stem+'-C.wav',
                    description='同一16毫秒参数事件触发三次，间隔用于试听；不是完整回火，也没有加入持续DNA或房间。'))
            rows.append(row);print(name,row['status'],flush=True)
        notes=['521–522s: dashboard remains in second gear in the five nearby views; left hand moves near the door/thigh. No identified shift/afterfire.',
               '142.437s: first gear visible in a stationary/slow steering context; pedal state and physical event identity unconfirmed.',
               '785.754s: first gear visible during driving; no directly identifiable event action.',
               'All six dashboard sheets and six timelines were visually inspected. Original audio supplied for human classification, not claimed acoustically identified.']
        report.update(result='passed',selection=rows,visual_observations=notes,scan_candidates=len(scan['candidates']),
            scan_qualified=sum(r['both_full_band_above_3db'] for r in scan['candidates']),new_download=False,
            all_sources_unprocessed=True,global_event_bank_changed=False)
        save(review/'report.json',report)
        paragraphs=['这页核查已批准B素材中排名前六的短响。原声保留双声道与原始样本，只统一乘0.25监听。',
            '短窗找到了原100毫秒窗口容易稀释的声音，但这六处都尚未确认是回火或换挡。参数候选只用于诊断，不接自动驾驶触发。',
            '六处固定选区中，四处频谱拟合未通过，两处通过单种子拟合但都未通过多种子检查。本页保留失败证据，不能把它们当成已完成的回火音效。',
            '如出现C短声：它是从固定16毫秒选区提参后由实际C生成，间隔触发三次方便听辨；不是完整动作、也没有录音回放。低频峰和长尾受短窗限制。']
        links=[('report.json','筛选与实际C检查记录')]+[(f'B-{n}-frames.jpg',f'{n} 原画面') for n in range(1,7)]
        links += [(f'B-{n}-timeline.png',f'{n} 频谱') for n in range(1,7)]
        links += [(f'B-{r["rank"]}-parameters.zip',f'{r["rank"]} 可编辑参数') for r in rows if r.get('C_seeds')]
        for track in tracks:
            path=review/track['file'];info=sf.info(path)
            track.update(sha256=sha(path),frames=info.frames,channels=info.channels)
        text=page('短事件素材核查 V1',paragraphs,tracks,links,plot='B-1-timeline.png')
        text=text.replace('原素材与新旧C的高频能量起伏对照','B原声上下文频谱')
        (review/'index.html').write_text(text,encoding='utf-8')
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result='passed',fitted=sum('C_seeds' in r for r in rows),qualified=sum(r.get('multi_seed_qualified',False) for r in rows)),flush=True)


if __name__=='__main__':main()
