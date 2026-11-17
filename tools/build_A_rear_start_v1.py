"""Exterior startup parameters in the existing C controller and full-drive recipe."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from event_review import page
from research_archive_v1 import load, save, sha
from vehicle_controller import take, recipe
from vehicle_controller.native import Bridge
from vehicle_scenarios.capture import capture, replay
from vehicle_scenarios.scenario import sport_lifecycle


def capture_case(bridge, value, folder):
    folder.mkdir(parents=True, exist_ok=False)
    measured, rows, transitions = capture(bridge, value, folder)
    check = replay(bridge, value)
    assert check['pcm_sha256'] == measured['pcm_sha256']
    assert check['source_events'] == value['source_events']
    assert check['final_state'] == measured['final_state']
    assert measured['native_reconstruction_error'] < 2e-6
    assert all(measured['final_state'][k] == 0 for k in ('event_rejected','event_overflow','event_log_lost'))
    assert measured['final_state']['event_peak'] <= 4
    save(folder/'verification.json', dict(result='passed', measured=measured, replay=check))
    return measured


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--verification', type=Path, required=True)
    args = p.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_build.py')
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1')
    verify = load(args.verification/'report.json')
    assert verify['result'] == 'passed'
    profiles = {kind: load(verify['profiles'][kind]['document']) for kind in ('crank','catch')}
    old_crank = load(root.parent/'startup_timbre_v1/crank1/profile.json')
    bridge = Bridge(repo)
    selection = next(row['id'] for row in bridge.catalog if row['key']=='v10-moving35')
    initial = bridge.initial(selection)[0]
    initial.update(mode=1, ignition=0, start_id=0, gear=0, automatic=0, throttle=0., brake=.65,
                   gain=.25, backfire=0, legacy_event_gain=0., startup_gain=0., catch_gain=0.)
    initial['input'].update(source=0, valid=0, sequence=0, speed_mps=0., acceleration_mps2=0., tire_slip=0.)
    initial['events'].update(enabled=1, gain=.5, pitch=1., decay=1., texture=1., manual_sequence=0)
    initial['events']['levels'] = [0.,1.,0.,0.,0.,0.,0.]
    response = deepcopy(bridge.startup_defaults)
    # Engineering adjustment includes the existing8ms scheduled early-event delay.
    # The200Hz driver quantizes transitions; report actual C gap, do not call it ECU timing.
    response['crank_seconds'] = .588
    variants, captures = {}, {}
    report = dict(result='running', goal_complete=False, timbre_accepted=False,
                  physical_source_separated=False, physical_RPM_identified=False)
    try:
        for name, crank, catch_level in [('historical',old_crank,0.), ('early',profiles['crank'],0.),
                                          ('pair25',profiles['crank'],.25)]:
            control = deepcopy(initial)
            control['events']['levels'][2] = catch_level
            overrides = dict(crank=crank, catch=profiles['catch'])
            value = take.create(bridge,selection,control,overrides,response)
            started = deepcopy(control)
            started.update(ignition=1,start_id=1)
            take.append(value,round(.35*48000),started)
            value['frames'] = 8*48000
            folder = out/name
            measured = capture_case(bridge,value,folder)
            assert measured['final_state']['lifecycle']==4 and measured['final_state']['operating']==0
            native,_ = sf.read(folder/'native.wav',dtype='float32',always_2d=True)
            assert native.shape == (384000,23)
            starts = [r for r in value['source_events'] if r['action']==1]
            early = next(r for r in starts if r['type']==1)
            later = next(r for r in starts if r['type']==2)
            assert early['frame']==early['requested_frame'] and later['frame']==later['requested_frame']
            for prefix in ('legacy_event','startup','catch'):
                index = sum(row['channels'] for row in bridge.stems[:next(i for i,r in enumerate(bridge.stems) if r['name']==prefix)])
                count = next(r['channels'] for r in bridge.stems if r['name']==prefix)
                assert not np.any(native[:,index:index+count])
            event = native[:,19:].sum(axis=1)*2**-.5
            sf.write(folder/'event-monitor.wav',np.column_stack((event,event)),48000,subtype='FLOAT')
            variants[name] = dict(measurement=measured, take=value, actual_event_gap_seconds=(later['frame']-early['frame'])/48000)
            captures[name] = native
            print(name,'startup and replay passed',flush=True)
        assert all(np.array_equal(row[:,:19],captures['early'][:,:19]) for row in captures.values())
        assert all(row['take']['source_events']==variants['early']['take']['source_events'] for row in variants.values())
        assert all(row['measurement']['final_state']==variants['early']['measurement']['final_state'] for row in variants.values())
        sf.write(out/'continuous-monitor.wav',sf.read(out/'early/mix.wav',always_2d=True)[0]-
                 sf.read(out/'early/event-monitor.wav',always_2d=True)[0],48000,subtype='FLOAT')
        complete = deepcopy(initial)
        complete['events']['levels'] = [0.,1.,.25,1.,0.,0.,0.]
        complete['backfire']=1
        exhaust = load(root.parent/'event_full_envelope_v1/C4/event-profile.json')
        full_overrides = dict(crank=profiles['crank'],catch=profiles['catch'],afterfire=exhaust)
        full, scenario = sport_lifecycle(bridge,selection,full_overrides,complete,response)
        save(out/'full-scenario.json',scenario)
        full_result = capture_case(bridge,full,out/'full')
        assert full_result['final_state']['lifecycle']==0
        assert any(r['type']==3 and r['action']==1 for r in full['source_events'])
        preset = recipe.create(bridge,selection,full['initial'],'踏板驾驶',full_overrides,response)
        recipe.validate(bridge,preset)
        take.save(out/'controller-preset.json',preset)
        review = out/'review'
        review.mkdir()
        tracks=[]
        def add(label,source,file,description,scale):
            x,rate=sf.read(source,always_2d=True)
            sf.write(review/file,x*scale,rate,subtype='FLOAT')
            tracks.append(dict(label=label,file=file,description=description,gain=scale,
                frames=len(x),channels=x.shape[1],sha256=sha(review/file)))
        add('车外原声 · 完整4秒',root/'selection1/context-original.wav','reference.wav','原47–51秒，动作从0.6秒附近开始；混合录音。',.25)
        add('原声 · 早期580ms',root/'selection1/early-original.wav','early-reference.wav','拖转状早期声学阶段，没有物理分离或测得的曲轴RPM。',.25)
        add('原声 · 后续1.2秒',root/'selection1/later-original.wav','later-reference.wav','后续发动机建立，包含持续发动机。',.25)
        for kind,label in [('crank','早期纹理'),('catch','接火阶段')]:
            add('独立C · '+label,args.verification/kind/'27431.wav',kind+'.wav','同一OSC／共振事件池，非原音频播放；固定种子。',.25)
        for name,label in [('historical','历史车内早期纹理'),('early','新车外早期纹理'),('pair25','新早期＋接火25%')]:
            add('完整C启动 · '+label,out/name/'mix.wav',name+'.wav','8秒同一工程启动，其他19持续通道完全相同。',1.)
        add('只听新早期＋接火25%',out/'pair25/event-monitor.wav','events.wav','独立事件分轨汇总；相同C状态和控制。',1.)
        add('只听持续声源',out/'continuous-monitor.wav','continuous.wav','同一启动流程中的DNA／低频／细节及怠速，不含独立事件。',1.)
        add('完整32秒 · 启动／驾驶／收油／停车',out/'full/mix.wav','full.wav','纯合成整车演示；收油E候选仍未确认为物理回火。',1.)
        shutil.copy2(out/'controller-preset.json',review/'controller-preset.json')
        shutil.copy2(out/'full/lifecycle.vsltake.json',review/'full.take.json')
        for kind in ('crank','catch'):
            save(review/(kind+'-profile.json'),profiles[kind])
        shutil.copy2(root/'contexts1/A_rear_47/timeline.png',review/'curves.png')
        prose=[
            '新候选来自同一批准A录音的车外尾排段：早期47.60–48.18秒，后续48.18–49.38秒，背景47.0–47.25秒。固定选区后提参，没有换背景、播放原音频或添加房间处理。',
            '先听完整原声，再听两条原始阶段和独立C。阶段是声学选区，不等于已分离启动机或燃烧；后续片段包含持续发动机，整车同时提供接火0%／25%对照，避免把叠加变厚直接当成还原。',
            '三条8秒完整启动保持相同19持续通道和动作，历史版只用于比较旧车内早期纹理；新事件均来自车外。控制台启动时长0.588秒、220RPM拖转、1150RPM冲转／850RPM怠速仍是工程设定；并非原车RPM恢复。实际事件间隔见验证记录。',
            '32秒页内配方包括启动、运动自动挡加速、收油、制动降挡、停车和熄火。主DNA／F2怠速／新A启动／E短声仍是工程组合，各自保留来源；不能称作同一辆车一次录音的完整重建。',
            '原声和单次C统一乘0.25；整车主增益0.25、事件总量0.5，接火层25%。无房间处理、限幅或逐条响度补偿。停止独立窗口后载入配方，可调早期／接火／收油电平和启动响应；新音色尚未听评。']
        text=page('车外启动声源 · 同一C系统',prose,tracks,
                  [(name,name) for name in ('controller-preset.json','full.take.json','crank-profile.json','catch-profile.json')])
        text=text.replace('原素材与新旧C的高频能量起伏对照','原素材完整上下文与声学阶段')
        (review/'index.html').write_text(text,encoding='utf-8')
        save(review/'tracks.json',tracks)
        binding=load(root/'selection1/runtime.json')
        assert len(binding)==459 and all(sha(repo/name)==digest for name,digest in binding.items())
        report.update(result='passed',variants=variants,full=full_result,source_ABI=11,
            bridge_sha256=bridge.sha256,continuous_19channels_exact=True,notices_state_exact=True,
            runtime_voice_files_unchanged=459,review=str(review),source_only=True)
    except Exception as error:
        report.update(result='failed',error=repr(error))
        raise
    finally:
        save(out/'report.json',report)


if __name__=='__main__':
    main()
