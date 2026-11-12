"""Render raw-Hz candidates with the already-qualified, unchanged C OSC cloud."""
import argparse
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--audit',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from hf_bandwidth_v1.observe import compare
from residual_dense_v1.oracle import read,counts,render as oracle

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.hf-bandwidth-render/1',result='running',human_accepted=False,
       device_checked=False,runtime_changed=False,commands=[],contexts=[],source_sha256={},input_sha256={})
try:
    audit=json.loads((a.audit/'report.json').read_text(encoding='utf-8'))
    assert audit['result']=='raw_Hz_observed_candidates_exported'
    r['input_sha256'][str(a.audit/'report.json')]=sha(a.audit/'report.json')
    # Reuse a binary only when its recorded linked sources still match.
    build_path=a.workspace/'references/analysis/residual_dense_v1/build1/report.json'
    build=json.loads(build_path.read_text(encoding='utf-8'));assert build['result']=='pass'
    for name,digest in build['source_sha256'].items():assert sha(repo/name)==digest,name
    probe=next(Path(name) for name in build['binaries'] if name.endswith('residual_dense_probe.exe'))
    assert sha(probe)==build['binaries'][str(probe)]
    (a.out/'bin').mkdir();shutil.copy2(probe,a.out/'bin'/probe.name);probe=a.out/'bin'/probe.name
    r['input_sha256'][str(build_path)]=sha(build_path);r['input_sha256'][str(probe)]=sha(probe)
    paths=[Path(__file__),repo/'tools/hf_bandwidth_v1/observe.py',
           repo/'tools/residual_dense_v1/oracle.py',repo/'tools/residual_osc_v1/spectrum.py',
           repo/'tools/drive_evidence_v1/sources.py',
           *(repo/name for name in build['source_sha256'])]
    for path in set(paths):
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        r['source_sha256'][name]=sha(path)
    listening=a.out/'listening';listening.mkdir()
    def review(name,audio):
        y=audio.copy()*.25
        n=min(960,len(y)//2);fade=np.sin(np.linspace(0,np.pi/2,n))**2
        y[:n]*=fade[:,None];y[-n:]*=fade[::-1,None]
        assert np.max(abs(y))<.95
        sf.write(listening/name,y,48000,subtype='PCM_24')
    for context in audit['contexts']:
        key=context['key'];folder=a.audit/key
        profile=folder/'raw_Hz_candidate.residual'
        assert sha(profile)==context['candidate_sha256']
        target,rate=sf.read(folder/'raw_reference_float.wav',always_2d=True)
        base,base_rate=sf.read(folder/'C_base_float.wav',always_2d=True)
        assert rate==base_rate==48000
        bands=[row['hz'] for row in context['budget']]
        moments=read(profile);carrier_counts=counts(moments,64);trials=[]
        for seed in (8121907,23117,61927):
            output=a.out/f'{key}_{seed}_cloud.wav'
            cmd=list(map(str,[probe,profile,output,'8','1','1',seed,'64','512']))
            done=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
            r['commands'].append(dict(argv=cmd,exit_code=done.returncode,stdout=done.stdout,stderr=done.stderr))
            done.check_returncode()
            cloud,cloud_rate=sf.read(output,always_2d=True)
            assert cloud_rate==48000 and len(cloud)==384000 and np.isfinite(cloud).all()
            expected=oracle(moments,carrier_counts,seed,2048)
            maximum=float(np.max(abs(cloud[:len(expected)]-expected)))
            assert maximum<6e-8,maximum
            y=base[:288000]+cloud[96000:]
            trial=dict(seed=seed,direct_OSC_error_FS=maximum,
                       baseline_errors=compare(target,base,bands),
                       candidate_errors=compare(target,y,bands))
            trials.append(trial)
            if seed==8121907:
                review(f'{key}_reference.wav',target)
                for amount in (0,.5,1):review(f'{key}_{amount:g}.wav',base[:288000]+amount*cloud[96000:])
        r['contexts'].append(dict(key=key,name=context['name'],trials=trials,
            control='Independent linear HF layer gain; 0/.5/1. Fixed root and static covariance, no state fit',
            amount_one_power_error_db_max=max(abs(v) for t in trials for row in t['candidate_errors'] for v in row['power_delta_db']),
            half_sensitivity_db_max=max(abs(10*np.log10(p/q)) for row,other in zip(context['raw_halves'][0],context['raw_halves'][1])
                                       if row['hz'][0]>=3000 for p,q in zip(row['power'],other['power']))))
    # Offline audition, not a real-time UI, matched action, or human acceptance.
    page=['<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
          '<title>原始频带与OSC补充核查</title><style>body{font:16px system-ui;max-width:900px;margin:32px auto;padding:0 20px;background:#f6f7f8;color:#17212b}section{background:white;padding:20px;margin:20px 0;border-radius:12px}audio{width:100%}p{line-height:1.7}</style>',
          '<h1>原始频带与 OSC 补充核查</h1><p>独立诊断候选，尚未获得听感认可。保留原DNA、相同输出增益0.25；没有逐条响度补偿。高频量是线性幅度。参考较短，C为持续声，不能比较整段动作或推断真实RPM。</p>',
          '<p>启动组仅补8–16kHz，不包含另一个300–8000Hz候选；驻车低音高组补3–16kHz。两种录音视角分别拟合。补充层只沉淀平均左右声纹，尚未还原状态／瞬态变化。</p>']
    for c in r['contexts']:
        page.append('<section><h2>'+html.escape(c['name'])+'</h2>')
        for label,suffix in [('原始录音短参考','reference'),('只听原DNA','0'),('独立补充层50%','0.5'),('独立补充层100%','1')]:
            page.append(f'<p>{label}</p><audio controls preload="none" src="listening/{c["key"]}_{suffix}.wav"></audio>')
        page.append('</section>')
    page.append('<script>document.addEventListener("play",e=>{if(e.target.tagName==="AUDIO")document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>')
    (a.out/'index.html').write_text('\n'.join(page),encoding='utf-8')
    r.update(result='unchanged_C_raw_Hz_candidates_rendered',limits=[
        'Mean power match is not recovery of HF timbral identity, transient structure or naturalness',
        'Only fixed acoustic anchors; no new RPM/load/state mapping or native UI/take change',
        'Fixed carrier beats remain possible; density64 is a fixed engineering comparison, not an accepted optimum',
        'No browser interaction, new device run, long-run or multichannel physical validation'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],contexts=[dict(key=c['key'],max_mean_power_error_db=c['amount_one_power_error_db_max'],
    max_half_sensitivity_db=c['half_sensitivity_db_max']) for c in r['contexts']])))
