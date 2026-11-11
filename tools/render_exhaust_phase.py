"""Independent causal phase audition over frozen V016 driving inputs."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from runtime_review import ROOT,sha,rms
from review_pairs import common_pair
from reference_segments import read_segment
from comparison_page import comparison_page
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'renders/exhaust_phase_v1'
PROBE=ROOT/'build-experiment-exhaust-phase/Release/exhaust_phase_probe.exe'
VARIANTS={'base':0,'delay':1,'mild':2,'strong':3}
LABELS={'base':'原声基线','delay':'只延时 1 ms','mild':'相位色散 · Q 0.7','strong':'相位色散 · Q 1.4'}
CASES={'low':('1200 RPM · 低转','low_base'), 'mid':('4000 RPM · 带载','mid_base'),
    'high':('8000 RPM · 带载','high_base'),'neutral':('空挡补油与落转','neutral_base'),
    'lift':('收油与恢复','lift_base'),'drive':('30 秒运动自动挡','drive_base'),
    'high_character':('8000 RPM · 保留燃烧／机械各 65%','high_combined')}

def run(args):
    d=subprocess.run(list(map(str,args)),cwd=ROOT,check=True,capture_output=True,text=True,timeout=90)
    return d.stdout

def read(path):
    x,sr=sf.read(path,always_2d=True);assert sr==48000 and sf.info(path).subtype=='FLOAT' and np.isfinite(x).all()
    return x

def main():
    if (OUT/'results.json').exists():raise SystemExit('Preserve completed exhaust_phase_v1.')
    OUT.mkdir(parents=True,exist_ok=True)
    native=json.loads((ROOT/'renders/v0.16.0/verification.json').read_text());commands={};inputs={}
    for name,(label,take_name) in CASES.items():
        path=ROOT/f'renders/v0.16.0/{take_name}.vsltake'
        assert sha(path)==native['files'][path.name];inputs[str(path.relative_to(ROOT))]=sha(path)
    def render_case(name,tag):
        path=ROOT/f'renders/v0.16.0/{CASES[name][1]}.vsltake';prefix=OUT/f'{name}_{tag}'
        args=[PROBE,path,prefix,VARIANTS[tag],2];stdout=run(args);assert 'pass' in stdout
        return f'{name}_{tag}',dict(command=list(map(str,args)),stdout=stdout)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(render_case,name,tag) for name in CASES for tag in VARIANTS]
        for job in as_completed(jobs):
            key,value=job.result();commands[key]=value;print('rendered',key,flush=True)
    impulse={}
    for sr in [16000,48000,192000]:
        impulse[str(sr)]={}
        for tag,mode in VARIANTS.items():
            path=OUT/f'impulse_{sr}_{tag}.wav';run([PROBE,'impulse',path,sr,mode]);x,rate=sf.read(path,always_2d=True)
            assert rate==sr and len(x)==sr and np.array_equal(x[:,0],x[:,1])
            h=np.fft.rfft(x[:,0]);error=float(np.max(abs(abs(h)-1)));assert error<1e-6,(sr,tag,error)
            energy=float(np.sum(x[:,0]**2));assert abs(energy-1)<1e-6
            frequency=np.fft.rfftfreq(sr,1/sr);phase=np.unwrap(np.angle(h))
            delay=-np.gradient(phase,2*np.pi*frequency/sr)/sr*1000
            samples={str(hz):float(np.interp(hz,frequency,delay)) for hz in [100,260,1250,3100,6000] if hz<sr*.45}
            impulse[str(sr)][tag]=dict(sha256=sha(path),maximum_magnitude_error=error,energy=energy,
                group_delay_ms=samples,last_100ms_peak=float(abs(x[-sr//10:]).max()))
    # Read C impulse output, rather than restating its transfer formula.
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    for tag in VARIANTS:
        x,sr=sf.read(OUT/f'impulse_48000_{tag}.wav',always_2d=True);h=np.fft.rfft(x[:,0]);f=np.fft.rfftfreq(len(x),1/sr)
        axes[0].semilogx(f[1:],20*np.log10(abs(h[1:])),label=tag)
        gd=-np.gradient(np.unwrap(np.angle(h)),2*np.pi*f/sr)/sr*1000
        axes[1].semilogx(f[1:],gd[1:],label=tag)
    axes[0].set(xlim=(30,16000),ylim=(-.001,.001),xlabel='Hz',ylabel='Magnitude / dB',title='C measured transfer: magnitude retained')
    axes[1].set(xlim=(30,16000),xlabel='Hz',ylabel='Group delay / ms',title='C measured transfer: frequency-dependent arrival')
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    fig.savefig(OUT/'transfer_response.png',dpi=160);plt.close(fig)
    rows={};pages={};objects=['exhaust_left','exhaust_right','intake','body','mechanical','air_left','air_right','events','road','wind']
    for name,(label,take_name) in CASES.items():
        arrays=[read(OUT/f'{name}_{tag}.wav') for tag in VARIANTS]
        assert all(abs(x).max()<.95 for x in arrays)
        assert (OUT/f'{name}_base.wav').read_bytes()==(ROOT/f'renders/v0.16.0/{take_name}.wav').read_bytes()
        assert (OUT/f'{name}_base.csv').read_bytes()==(ROOT/f'renders/v0.16.0/{take_name}.csv').read_bytes()
        assert all((OUT/f'{name}_{tag}.csv').read_bytes()==(OUT/f'{name}_base.csv').read_bytes() for tag in VARIANTS)
        unaffected={}
        for tag in VARIANTS:
            unaffected[tag]=[s for s in objects if (OUT/f'{name}_{tag}_source_{s}.wav').read_bytes()==(OUT/f'{name}_base_source_{s}.wav').read_bytes()]
            assert set(objects)-{'exhaust_left','exhaust_right','body'}<=set(unaffected[tag])
        auditions=common_pair(OUT,arrays,list(VARIANTS),name)
        rows[name]=dict(take=take_name,commands={tag:commands[f'{name}_{tag}'] for tag in VARIANTS},auditions=auditions,
            identical_driving_trace=True,unaffected_sources=unaffected,
            raw_mix_rms_dbfs={tag:rms(x) for tag,x in zip(VARIANTS,arrays)})
        pages[name]=dict(label=label,takes={tag:'../renders/exhaust_phase_v1/'+auditions[tag]['file'] for tag in VARIANTS},
            gain_note=f'四版同一输入，共用固定增益 {auditions["base"]["gain_db"]:+.2f} dB；保留实际混音电平差异。')
        if name in ['low','mid','high']:
            banks=[np.column_stack([read(OUT/f'{name}_{tag}_source_{s}.wav')[:,0] for s in ['exhaust_left','exhaust_right']]) for tag in VARIANTS]
            solo=common_pair(OUT,banks,list(VARIANTS),name+'_sources');rows[name]['source_auditions']=solo
            pages[name+'_sources']=dict(label=label+' · 两排气源独奏（非耳朵位置）',
                takes={tag:'../renders/exhaust_phase_v1/'+solo[tag]['file'] for tag in VARIANTS},
                gain_note=f'左右是两个源对象，共用独奏增益 {solo["base"]["gain_db"]:+.2f} dB；不代表最终立体声响度。')
    # Shared source content in the future bed uses the same explicit transfer state.
    args=[PROBE,ROOT/'renders/v0.16.0/high_base.vsltake',OUT/'high_strong_714',3,12];run(args)
    for source in objects:assert (OUT/f'high_strong_714_source_{source}.wav').read_bytes()==(OUT/f'high_strong_source_{source}.wav').read_bytes()
    assert (OUT/'high_strong_714.csv').read_bytes()==(OUT/'high_strong.csv').read_bytes()
    scene_path=OUT/'high_strong_714_scene.json';scene=json.loads(scene_path.read_text());scene['base_dsp_version']=scene.pop('dsp_version')
    scene['experiment']='exhaust_phase_v1 strong; engineering allpass, not measured acoustic transfer'
    for obj in scene['objects']:
        p=__import__('pathlib').Path(obj['file']);obj['sha256']=sha(p);obj['file']=p.name
    scene_path.write_text(json.dumps(scene,indent=2),encoding='utf-8')
    reference={}
    for name,identity,use in [('low','A_exterior_low_rev','exterior_spectral_observation'),('blips','A_exterior_blips','exterior_dynamic_observation')]:
        x,sr,prov=read_segment(identity,use);n=round(.005*sr);fade=np.ones(len(x));fade[:n]=.5-.5*np.cos(np.linspace(0,np.pi,n));fade[-n:]=fade[:n][::-1]
        path=OUT/f'reference_A_{name}.wav';sf.write(path,x*.5*fade[:,None],sr,subtype='PCM_24')
        reference[name]=dict(provenance=prov,sha256=sha(path),file=path.name,
            processing='Fixed .5 gain (-6.0206dB); 5ms cosine endpoint fades; PCM24. No HP, normalization, denoise or channel sum.')
    page=comparison_page(title='主排气相位成形 · 实验 1',version='EXHAUST PHASE 1 · EXPERIMENT',
        headline='比较排气波形的尖峰与拖尾',intro='<p>现有幅度谱已经随转速和工况变化。本实验单独改变声学相位关系，比较固定延时与两种相位色散。先听 4000／8000 RPM，再听空挡和收油。</p>',
        cases=pages,methods=LABELS,extra='<p>关注整体电子感、尖峰、拖尾，以及是否变闷或出现金属腔感。全通单独作用于两个排气源；完整混音可能因与其他声层干涉而改变电平。此页是固定驾驶输入的离线试听，原生 V016 配方未改。</p><details><summary>批准的车外参考（不同工况、录音与增益，不能当匹配台架）</summary><p>低转 208–211 秒</p><audio data-reference controls preload="metadata" src="../renders/exhaust_phase_v1/reference_A_low.wav"></audio><p>驻车补油 238–248 秒</p><audio data-reference controls preload="metadata" src="../renders/exhaust_phase_v1/reference_A_blips.wav"></audio></details>',
        footer='<p><a href="主排气相位成形实验V1.md">方法、参数与验证边界</a></p>')
    (ROOT/'research/主排气相位成形试听V1.html').write_text(page,encoding='utf-8')
    result=dict(experiment='exhaust_phase_v1',base_runtime='0.16.0',seed=48271,inputs=inputs,variants=VARIANTS,cases=rows,
        impulse=impulse,references=reference,source_objects=10,stereo_bed_source_match=True,
        mechanism='Causal second-order allpass cascade at existing engineering formants 260/1250/3100Hz, Q .7 or1.4; both banks same transfer. Delay control1ms. No extra OSC, noise, nonlinearity, reference playback or per-setting normalization.',
        subjective='Unaccepted exploratory phase comparison, not a measured manifold or demonstrated improvement.',
        binaries={str(PROBE.relative_to(ROOT)):sha(PROBE),'build-v016/Release/vsl_core.lib':sha(ROOT/'build-v016/Release/vsl_core.lib')})
    result['files']={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Phase audition: 7 mixes x4, 3 two-source groups x4, 12 C impulses and matched714 sources pass.',flush=True)

if __name__=='__main__':main()
