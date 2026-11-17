"""Stage a fixed E short-sound candidate in the real C pool, workbench and driver."""
import argparse
import base64
from copy import deepcopy
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from event_authoring.audio import read
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from event_designer.workspace import EventWorkspace
from event_review import page
from vehicle_controller.native import Bridge, Engine
from vehicle_controller import take, recipe
from vehicle_scenarios.capture import replay
from research_archive_v1 import load, save, sha


EDGES=((0,60),(60,300),(300,1200),(1200,4500),(4500,14000),(14000,24001))


def psd(x):
    """Explicit channel-mean periodic-Hann rFFT, without production Welch code."""
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    n=min(2048,len(x));window=.5-.5*np.cos(2*np.pi*np.arange(n)/n)
    values=[]
    for first in range(0,len(x)-n+1,n//2):
        z=np.fft.rfft(x[first:first+n]*window[:,None],axis=0)
        power=(z.real*z.real+z.imag*z.imag)/(48000*np.dot(window,window))
        power[1:-1]*=2
        values.append(power.mean(axis=1))
    return np.fft.rfftfreq(n,1/48000),np.mean(values,axis=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/low_mid_event_scan_v1')
    report=dict(result='running',goal_complete=False,timbre_accepted=False,physical_identity_confirmed=False)
    shutil.copy2(__file__,out/'executed_build.py')
    try:
        doc=load(root/'E-candidate1/profile.json');job=load(repo/'research/E_low_mid_event_v1.job.json')
        assert doc['source_job']==job and not doc['physical_identity_confirmed']
        master=Path(job['source']);x,rate,origin=read(master,*job['seconds'])
        background,_,_=read(master,*job['background_seconds'])
        assert origin['first_frame']==687120 and origin['last_frame']==691920
        f,power=psd(x);fb,bp=psd(background);bp=np.interp(f,fb,bp)
        target=np.maximum(power-bp,0);df=f[1]-f[0]
        targets=np.array([target[(f>=lo)&(f<hi)].sum()*df for lo,hi in EDGES]);total=targets.sum()
        fitted=doc['fit']['source_response_fit']['bands']
        assert np.max(abs(targets-np.array([r['target_power'] for r in fitted])))<1e-14
        renderer=Renderer(repo);seeds=[]
        for seed in (27431,48271,93931,17389):
            wave,metadata=renderer.render(doc['parameters'],doc['kind'],dict(seconds=.5,seed=seed))
            expected=synth(doc['parameters'],seed=seed,seconds=.5);expected=np.pad(expected,(0,len(wave)-len(expected)))
            error=float(np.max(abs(wave-expected)));assert error<3e-7
            frequency,spectrum=psd(wave[:len(x)])
            generated=np.array([spectrum[(frequency>=lo)&(frequency<hi)].sum()*df for lo,hi in EDGES])
            rows=[]
            for band,tar,actual in zip(EDGES,targets,generated):
                db=float(10*np.log10(max(actual,1e-30)/max(tar,1e-30)))
                significant=tar>=total*1e-4
                passed=abs(db)<=3 if significant else actual<=max(tar*2,total*2e-4)
                rows.append(dict(hz=band,target_power=float(tar),generated_power=float(actual),error_db=db,passed=bool(passed)))
            sf.write(out/f'C-{seed}.wav',wave,rate,subtype='FLOAT');save(out/f'C-{seed}.json',metadata)
            seeds.append(dict(seed=seed,independent_model_error_FS=error,bands=rows,passed=all(r['passed'] for r in rows)))
        report['C_seeds']=seeds
        assert all(row['passed'] for row in seeds),seeds
        context,_,provenance=read(master,13.34,15.84)
        sf.write(out/'original-context.wav',context,rate,subtype='FLOAT')
        sf.write(out/'original-crop.wav',x,rate,subtype='FLOAT')
        workspace=EventWorkspace(repo,Path('E:/VehicleSoundLab/designs/events'))
        project=workspace.create(dict(filename='E_13.34-15.84_low-mid-candidate.wav',
            audio=base64.b64encode((out/'original-context.wav').read_bytes()).decode(),kind='afterfire',viewpoint='exterior'))
        project=workspace.scan_candidates(dict(id=project['id'],scan_detector='low_mid'))
        index=next(i for i,r in enumerate(project['candidate_scan']['candidates']) if abs(r['source_seconds']-1)<.005)
        project=workspace.use_candidate(dict(id=project['id'],scan_run=project['scan_run'],candidate_index=index))
        project=workspace.analyze(dict(id=project['id'],name=job['name'],seconds=[.975,1.075],
            background_seconds=[.65,.85],response_fit='source-response-v1',context=job['context']+' Original context begins13.34s.',gated=False))
        assert project['document']['parameters']==doc['parameters']
        project=workspace.render(dict(id=project['id'],controls=controls(dict(seconds=.5))))
        version=workspace.root/project['id']/project['last_version']
        pcm,_=sf.read(version/'synthesis.wav',dtype='float32')
        expected,_=sf.read(out/'C-27431.wav',dtype='float32');assert np.array_equal(pcm,expected)
        shutil.copytree(workspace.root/project['id'],out/'editable-project')
        report['workbench']=dict(project_id=project['id'],parameters=str(version/'parameters.json'),
            reextraction_parameters_exact=True,actual_C_PCM_exact=True,low_mid_selection_context_saved=True)
        print('Four actual C seeds, independent spectra and editable project passed',flush=True)
        bridge=Bridge(repo);assert bridge.abi()==11
        selection=next(r['id'] for r in bridge.catalog if r['key']=='v10-moving35')
        initial=bridge.initial(selection)[0]
        initial.update(mode=1,ignition=1,start_id=1,gear=0,automatic=0,throttle=0.,brake=.7,gain=.25,backfire=1)
        initial['events'].update(enabled=1,gain=.5,pitch=1.,decay=1.,texture=1.,manual_sequence=0)
        initial['events']['levels']=[0.,0.,0.,1.,0.,0.,0.]
        overrides={'afterfire':doc};startup=deepcopy(bridge.startup_defaults)
        on=take.create(bridge,selection,initial,overrides,startup);on['frames']=8*48000
        control=deepcopy(initial)
        for seconds,changes in ((1.7,dict(throttle=.65)),(3.7,dict(throttle=0.)),(5.,dict(throttle=.45)),(6.5,dict(throttle=0.))):
            control.update(changes);take.append(on,round(seconds*48000),control)
        off=deepcopy(on)
        for c in [off['initial']]+[r['control'] for r in off['events']]:c['events']['levels'][3]=0.
        captures={};native=[]
        for name,value in [('off',off),('on',on)]:
            mix=[];stems=[];notices=[];index=0
            with Engine(bridge,selection,overrides,startup) as engine:
                engine.set(value['initial'])
                while engine.frame<value['frames']:
                    pcm,index=take.replay_block(engine,value,index,240)
                    mix.append(np.frombuffer(pcm,dtype='<f4').reshape(-1,2).copy())
                    stems.append(np.ctypeslib.as_array(engine.stems)[:240*bridge.channels()].reshape(240,-1).copy())
                    notices.extend(engine.last_events)
                state=engine.state()
            value['source_events']=notices;joined=np.concatenate(mix);separate=np.concatenate(stems)
            assert separate.shape==(384000,23)
            captures[name]=dict(mix=joined,stems=separate,state=state,events=notices)
            sf.write(out/('drive-'+name+'.wav'),joined,rate,subtype='FLOAT')
            sf.write(out/('native-'+name+'.wav'),separate,rate,subtype='FLOAT')
            take.save(out/('drive-'+name+'.take.json'),value)
        assert np.array_equal(captures['on']['stems'][:,:19],captures['off']['stems'][:,:19])
        assert captures['on']['events']==captures['off']['events']
        assert captures['on']['state']==captures['off']['state']
        event=captures['on']['stems'][:,19:].sum(axis=1)*2**-.5
        event_mix=np.column_stack([event,event]);sf.write(out/'drive-events.wav',event_mix,rate,subtype='FLOAT')
        error=float(np.max(abs(captures['on']['mix'].astype(float)-captures['off']['mix']-event_mix)))
        assert error<2e-7
        starts=[r for r in on['source_events'] if r['type']==3 and r['action']==1]
        assert len(starts)>=2 and all(r['frame']==r['requested_frame'] for r in starts)
        check=replay(bridge,on)
        import hashlib
        assert check['pcm_sha256']==hashlib.sha256(captures['on']['mix'].astype('<f4').tobytes()).hexdigest()
        assert check['source_events']==on['source_events'] and check['final_state']==captures['on']['state']
        take.save(out/'controller-preset.json',recipe.create(bridge,selection,initial,'踏板驾驶',overrides,startup))
        save(out/'event-profile.json',doc)
        report['driver']=dict(frames=on['frames'],continuous_19channels_exact=True,notices_exact=True,
            final_state_exact=True,variable_block_replay_exact=True,starts=starts,mix_error_FS=error,
            bridge_sha256=bridge.sha256,source_ABI=11,final_state=captures['on']['state'])
        review=out/'review';review.mkdir();tracks=[]
        def add(label,source,file,description,scale=.25):
            wave,sr=sf.read(source,always_2d=True);sf.write(review/file,wave*scale,sr,subtype='FLOAT')
            tracks.append(dict(label=label,file=file,description=description,gain=scale,frames=len(wave),channels=wave.shape[1],sha256=sha(review/file)))
        add('E 原声 · 2.5秒上下文',out/'original-context.wav','context.wav','原始13.34–15.84秒；短声约在第1秒，之后还有一次补油。')
        add('E 原声 · 固定100ms选区',out/'original-crop.wav','crop.wav','混合录音；不是已分离的物理回火。')
        for seed in (27431,48271,93931,17389):add('纯合成 C · 种子'+str(seed),out/f'C-{seed}.wav',f'C-{seed}.wav','实际同一C事件池；100ms声音，其后静音；未做响度归一化。')
        for name,label in [('off','短声关闭'),('on','短声开启'),('events','只听事件')]:
            add('C 补油收油 · '+label,out/('drive-'+name+'.wav'),'drive-'+name+'.wav','8秒工程动作，由踏板触发；主DNA保持。',scale=1.)
        for file in ('event-profile.json','controller-preset.json','drive-on.take.json'):shutil.copy2(out/file,review/file)
        fig,axes=plt.subplots(2,1,figsize=(10,5.5),layout='constrained')
        axes[0].plot(f,10*np.log10(np.maximum(target,1e-30)),label='Recorded positive PSD excess')
        frequency,spectrum=psd(expected[:len(x)])
        axes[0].plot(frequency,10*np.log10(np.maximum(spectrum,1e-30)),label='Actual C / seed27431')
        axes[0].set(xlim=(0,4500),ylim=(-100,-10),xlabel='Hz',ylabel='PSD / FS2 per Hz');axes[0].legend()
        axes[1].plot(np.arange(len(event))/rate,event,lw=.7);axes[1].set(xlabel='Generated seconds',ylabel='Event monitor / FS')
        for ax in axes:ax.grid(alpha=.2)
        fig.savefig(review/'curves.png',dpi=140);plt.close(fig)
        prose=['这是E驻车降转后约14.34秒的低中频短声候选；本轮补上低中频扫描，再由同一纯合成事件核生成。物理回火身份和听感尚未确认。',
            '先听原声上下文第1秒，再比较固定选区与C单次。选区只长100ms，不代表已还原完整首尾；原声含持续发动机和现场背景，C只拟合统计增量。四个随机种子均保留相同原始电平。',
            '8秒补油／收油是工程触发演示；主DNA、低频和细节19通道逐样本相同，差值来自独立事件分轨。它没有复制视频RPM轨迹，也没有把此短声与先前13.309秒高频事件拼成一条回火。',
            '参考和单次C统一乘0.25；驾驶对照使用同一主增益0.25，事件增益0.5。没有房间处理、压缩、PCM循环或逐条响度补偿。控制窗口停止后载入本页配方，即可用油门补油，松开自动触发。']
        text=page('低中频短声 · 纯合成与收油触发',prose,tracks,[(f,f) for f in ('event-profile.json','controller-preset.json','drive-on.take.json')])
        text=text.replace('原素材与新旧C的高频能量起伏对照','原素材声学增量频谱、实际C频谱及独立事件分轨')
        (review/'index.html').write_text(text,encoding='utf-8');save(review/'tracks.json',tracks)
        baseline=load(root/'before/runtime.json');assert all(sha(repo/name)==value for name,value in baseline.items())
        report.update(result='passed',original_source=provenance,formal_runtime_voice_files_unchanged=len(baseline),
            review=str(review),local_candidate_only=True,runtime_uses_recording=False)
    except Exception as error:report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result='passed',project=report['workbench']['project_id'],review=str(review)),flush=True)


if __name__=='__main__':main()
