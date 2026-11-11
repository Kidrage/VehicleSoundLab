"""Isolated pressure/structure auditions over identical frozen V015 takes."""
import csv
import json
import subprocess
from pathlib import Path
from runtime_review import ROOT,sha,rms
from review_pairs import common_pair
from comparison_page import comparison_page
import numpy as np
import soundfile as sf

OUT=ROOT/'renders/character_v1'
PROBE=ROOT/'build-experiment-character/Release/character_probe.exe'
FROZEN=ROOT/'baselines/v0.15.0/bin/vsl_take_render.exe'
VARIANTS={'base':(0,0),'pressure':(1,0),'structure':(0,1),'combined':(.65,.65)}
LABELS={'base':'当前基线','pressure':'加强逐次压力','structure':'加强机械结构','combined':'两层合用 · 各 65%'}
CASES={
    'low':('1200 RPM · 低转','fixed',5,1200,.18),
    'mid':('4000 RPM · 带载','fixed',5,4000,.85),
    'high':('8000 RPM · 带载','fixed',5,8000,.85),
    'neutral':('空挡 · 补油与落转','neutral',8,850,.18),
    'lift':('5000 RPM · 收油与恢复','lift',7.5,5000,.85),
    'drive':('运动自动挡 · 30 秒驾驶','auto',30,850,.18),
}
OBJECTS=['exhaust_left','exhaust_right','intake','body','mechanical','air_left','air_right','events','road','wind']


def command(args):
    result=subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True,timeout=90)
    return dict(command=list(map(str,args)),stdout=result.stdout)


def read_audio(path):
    x,rate=sf.read(path,always_2d=True);assert rate==48000 and sf.info(path).subtype=='FLOAT'
    assert np.isfinite(x).all() and abs(x).max()<.95
    return x


def main():
    if (OUT/'results.json').exists():raise SystemExit('Preserve completed character_v1 review; use a new experiment.')
    OUT.mkdir(parents=True,exist_ok=True)
    result=dict(experiment='character_v1',base_runtime='0.15.0',default_runtime_changed=False,seed=48271,
        variants=VARIANTS,user_focus='Overall sound still electronic; strengthen per-firing combustion and mechanical detail first.',
        processing='No reference playback, air-gain change, coefficient replacement or separate loudness normalization. Common constant audition gain per group.',cases={})
    pages={}
    for name,(label,scenario,seconds,rpm,load) in CASES.items():
        capture=command([PROBE,'capture',OUT/name,scenario,seconds,rpm,load,0,0])
        take=OUT/f'{name}.vsltake';rows={};arrays=[];paths={};frozen=OUT/f'{name}_frozen.wav'
        command([FROZEN,take,frozen])
        for variant,(pressure,structure) in VARIANTS.items():
            prefix=OUT/f'{name}_{variant}';paths[variant]=prefix.with_suffix('.wav')
            run=command([PROBE,'render',take,prefix,pressure,structure,2])
            x=read_audio(paths[variant]);arrays.append(x)
            assert len(x)==round(seconds*48000) and x.shape[1]==2
            rows[variant]=dict(**run,rms_dbfs=rms(x),peak=float(abs(x).max()),sha256=sha(paths[variant]))
            assert 'pass' in run['stdout']
        assert paths['base'].read_bytes()==frozen.read_bytes(),name
        base_trace=(OUT/f'{name}_base.csv').read_bytes()
        for variant in VARIANTS:assert (OUT/f'{name}_{variant}.csv').read_bytes()==base_trace
        unaffected={}
        for variant in VARIANTS:
            same=[]
            for source in OBJECTS:
                before=OUT/f'{name}_base_source_{source}.wav';after=OUT/f'{name}_{variant}_source_{source}.wav'
                if before.read_bytes()==after.read_bytes():same.append(source)
            unaffected[variant]=same
        independent=['intake','air_left','air_right','events','road','wind']
        for variant in VARIANTS:assert set(independent)<=set(unaffected[variant])
        assert 'mechanical' in unaffected['pressure']
        assert {'exhaust_left','exhaust_right','body'}<=set(unaffected['structure'])
        # The shared stroke process is independent of which layer is auditioned.
        events={}
        for variant in VARIANTS:
            with (OUT/f'{name}_{variant}_character.csv').open() as f:events[variant]=list(csv.DictReader(f))
        signature=lambda rows:[(r['seconds'],r['rpm'],r['lifecycle'],r['fuel_command'],r['event_count'],r['energy_min'],r['energy_max']) for r in rows]
        assert all(signature(v)==signature(events['base']) for v in events.values())
        error=float(np.max(abs(arrays[3]-(arrays[0]+.65*(arrays[1]-arrays[0])+.65*(arrays[2]-arrays[0])))))
        assert error<1e-7
        audition=common_pair(OUT,arrays,list(VARIANTS),name)
        pages[name]=dict(label=label,takes={v:'../renders/character_v1/'+audition[v]['file'] for v in VARIANTS},
            gain_note=f'本组四版共用固定增益 {audition["base"]["gain_db"]:+.2f} dB；切换保留播放位置。合用版两层各 65%。')
        result['cases'][name]=dict(label=label,capture=capture,take_sha256=sha(take),variants=rows,auditions=audition,
            unaffected_sources=unaffected,identical_complete_driving_trace=True,identical_stroke_sequence=True,
            source_linear_combination_error=error,final_events=int(events['base'][-1]['event_count']))
        if scenario=='fixed':
            measurements={}
            for variant in VARIANTS:
                powers={}
                for source in ['exhaust_left','exhaust_right','mechanical']:
                    x=read_audio(OUT/f'{name}_{variant}_source_{source}.wav')[120000:230400]
                    powers[source]=float(np.mean(x*x))
                measurements[variant]=dict(mechanical_dbfs=float(10*np.log10(max(powers['mechanical'],1e-30))),
                    mechanical_to_separate_exhaust_power_sum_db=float(10*np.log10(powers['mechanical']/max(powers['exhaust_left']+powers['exhaust_right'],1e-30))))
            result['cases'][name]['stable_source_power']=measurements
        print('completed',name,flush=True)
    prefix=OUT/'high_combined_714';command([PROBE,'render',OUT/'high.vsltake',prefix,.65,.65,12])
    scene_path=OUT/'high_combined_714_scene.json';scene=json.loads(scene_path.read_text(encoding='utf-8'))
    scene['base_runtime_version']=scene.pop('dsp_version');scene['dsp_version']='character_v1 experiment'
    scene['experiment_parameters']=dict(pressure=.65,structure=.65)
    for obj in scene['objects']:
        path=Path(obj['file']);obj['sha256']=sha(path);obj['file']=path.name
    scene_path.write_text(json.dumps(scene,indent=2,ensure_ascii=False),encoding='utf-8')
    assert sf.info(prefix.with_suffix('.wav')).channels==12
    for source in OBJECTS:
        assert (OUT/f'high_combined_source_{source}.wav').read_bytes()==(OUT/f'high_combined_714_source_{source}.wav').read_bytes()
    assert (OUT/'high_combined.csv').read_bytes()==(OUT/'high_combined_714.csv').read_bytes()
    result['bed714']=dict(identical_ten_sources=True,identical_complete_driving_trace=True,scene='high_combined_714_scene.json',actual_array_listening=False)
    preserved={}
    for name in ['core/dna.c','core/high_orders.c','core/exhaust_spectrum.c','profiles/high_orders.c']:
        a=ROOT/'src'/name;b=ROOT/'baselines/v0.11.0/src'/name;assert a.read_bytes()==b.read_bytes();preserved[name]=sha(a)
    result['preserved_V011_source']=preserved
    page=comparison_page(title='燃烧与机械细节 · 实验 1',version='CHARACTER 1 · EXPERIMENT',
        headline='让每次燃烧更有实体感',intro='<p>保留你认可的连续声线，比较逐次压力和机械结构两种增强。先听 4000／8000 RPM，再听空挡与收油。</p>',
        cases=pages,methods=LABELS,
        extra='<p>注意电子嗡鸣是否减弱，以及是否出现过多敲击、金属振铃或毛刺。四版是同一驾驶过程；可分别判断哪一层值得保留。</p><p class="quiet">这是独立音色实验，当前主程序仍为 V015。尚未完成实车压力／结构标定。</p>',
        footer='<p><a href="燃烧与机械细节实验V1.md">实现与验证</a> · <a href="听评记录.md">已收到的听评</a></p>')
    (ROOT/'research/燃烧与机械细节试听V1.html').write_text(page,encoding='utf-8')
    result['binaries']={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [PROBE,ROOT/'build-v015/Release/vsl_core.lib']}
    result['files']={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('6 identical-take groups x 4 variants; frozen compatibility, independent stems and 7.1.4 contracts pass.',flush=True)


if __name__=='__main__':main()
