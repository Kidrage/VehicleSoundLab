"""Bind raw-Hz evidence, verify published audio, and freeze this diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--audit',type=Path,required=True)
p.add_argument('--render',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.hf-bandwidth-verification/1',result='running',http_and_decode=[],generated_input_sha256={})
try:
    audit=json.loads((a.audit/'report.json').read_text(encoding='utf-8'))
    render=json.loads((a.render/'report.json').read_text(encoding='utf-8'))
    assert audit['result']=='raw_Hz_observed_candidates_exported'
    assert render['result']=='unchanged_C_raw_Hz_candidates_rendered'
    for root,record in ((a.audit,audit),(a.render,render)):
        for name,digest in record['source_sha256'].items():
            assert sha(repo/name)==sha(root/'exact_sources'/name)==digest,name
        for name,digest in record['input_sha256'].items():assert sha(name)==digest,name
    # Confirm generated raw/C files against their original sources, rather
    # than trusting mutable intermediates simply because a report exists.
    frozen_inputs=[
        ('startup','A_start_context','audio_onset_observation','startup_catch_v1',
         'evidence/render1/renders/fixed_1.0.wav'),
        ('stationary_low','A_exterior_blips','exterior_dynamic_observation','exterior_anchors_v1',
         'evidence/anchors_v2/A Stationary Low/raw_1.0.wav')]
    for key,segment,use,folder,name in frozen_inputs:
        c=next(c for c in audit['contexts'] if c['key']==key)
        raw,provenance=read(a.workspace,segment,use)
        begin,end=[round((s-provenance['seconds'][0])*48000) for s in c['seconds']]
        expected=raw[begin:end]
        observed,rate=sf.read(a.audit/key/'raw_reference_float.wav',always_2d=True)
        assert rate==48000 and np.array_equal(expected,observed)
        original,rate=sf.read(a.workspace/'baselines'/folder/name,always_2d=True)
        observed,rate2=sf.read(a.audit/key/'C_base_float.wav',always_2d=True)
        assert rate==rate2==48000 and np.array_equal(original[96000:],observed)
    for file in a.audit.rglob('*'):
        if file.is_file() and file.suffix in ('.wav','.residual'):r['generated_input_sha256'][str(file)]=sha(file)
    # Check all eight audio links and the page over the actual local server.
    files=[a.render/'index.html',*sorted((a.render/'listening').glob('*.wav'))]
    assert len(files)==9
    for file in files:
        url='http://127.0.0.1:8789/'+file.relative_to(a.workspace).as_posix()
        with urllib.request.urlopen(url,timeout=10) as response:payload=response.read()
        assert hashlib.sha256(payload).hexdigest()==sha(file)
        item=dict(file=file.relative_to(a.workspace).as_posix(),url=url,sha256=sha(file),http_byte_equal=True)
        if file.suffix=='.wav':
            cmd=['ffmpeg','-v','error','-i',str(file),'-f','null','-']
            done=subprocess.run(cmd,capture_output=True,timeout=30);assert done.returncode==0,done.stderr
            y,rate=sf.read(file,always_2d=True)
            assert rate==48000 and y.shape[1]==2 and np.isfinite(y).all()
            item.update(ffmpeg_decode=True,peak_FS=float(np.max(abs(y))),frames=len(y))
        r['http_and_decode'].append(item)
    # Publication figure: observational band powers, not aligned waveforms.
    fig,axes=plt.subplots(2,1,figsize=(11,7),constrained_layout=True)
    indices=list(range(2,8));x=np.arange(len(indices));width=.24
    for axis,c in zip(axes,audit['contexts']):
        for j,(label,key) in enumerate((('Raw recording','raw'),('Normalized reference','normalized'),('C DNA','C'))):
            db=[10*np.log10(max(1e-15,np.mean(c[key][i]['power']))) for i in indices]
            axis.bar(x+(j-1)*width,db,width,label=label)
        axis.set_xticks(x,[f'{c["raw"][i]["hz"][0]/1000:g}-{c["raw"][i]["hz"][1]/1000:g}' for i in indices])
        axis.set_ylim(-150,-20);axis.set_ylabel('Mean L/R band power (dBFS)')
        axis.set_xlabel('Frequency band (kHz)');axis.set_title(c['name'])
        axis.grid(axis='y',alpha=.2);axis.set_axisbelow(True)
    axes[0].legend(loc='lower left',ncols=3)
    fig.savefig(a.out/'bandwidth.png',dpi=150);plt.close(fig)
    r.update(result='pass',indexed_C_H_unchanged=audit['indexed_C_H_unchanged'],
             new_CTests_run=False,new_device_test=False,browser_interaction=False,human_accepted=False)
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    docs=['AGENTS.md','README.md','handoff/算法说明.md','handoff/声纹沉淀与控制边界.md','research/原始高频覆盖V1.md']
    tools=['tools/audit_hf_bandwidth_v1.py','tools/hf_bandwidth_v1/observe.py',
           'tools/render_hf_bandwidth_v1.py','tools/finalize_hf_bandwidth_v1.py']
    def hashes(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    summary=dict(schema='vsl.hf-bandwidth-summary/1',result='raw_Hz_static_OSC_diagnostic_only',date='2026-11-12',
        contexts=[dict(key=c['key'],name=c['name'],seconds=c['seconds'],
                       highest_retained_DNA_line_hz=c['highest_retained_line_hz'],
                       budget_bands=[dict(hz=row['hz'],accepted=row['accepted']) for row in c['budget']]) for c in audit['contexts']],
        C_results=render['contexts'],controls=audit['known_controls'],
        indexed_C_H_unchanged=audit['indexed_C_H_unchanged'],new_CTests_run=False,new_device_test=False,
        runtime_changed=False,native_UI_integrated=False,human_accepted=False,
        page='http://127.0.0.1:8789/'+(a.render/'index.html').relative_to(a.workspace).as_posix(),
        limits=audit['limits']+render['limits'],http_and_decode=r['http_and_decode'],
        current_source_sha256={name:sha(repo/name) for name in docs+tools},
        evidence_sha256={name:hashes(root) for name,root in [('audit1',a.audit),('render1',a.render),('verification1',a.out)]})
    summary_path=repo/'research/hf_bandwidth_v1_summary.json'
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    freeze=a.workspace/'baselines/hf_bandwidth_v1'
    assert freeze.resolve().is_relative_to(a.workspace.resolve()) and not freeze.exists()
    freeze.mkdir(parents=True)
    for name,root in [('audit1',a.audit),('render1',a.render),('verification1',a.out)]:
        shutil.copytree(root,freeze/'evidence'/name,ignore=shutil.ignore_patterns('__pycache__'))
    for name in docs+tools+['research/hf_bandwidth_v1_summary.json']:
        dest=freeze/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
    manifest=dict(schema='vsl.freeze/1',files=[dict(path=name,sha256=digest) for name,digest in hashes(freeze).items()])
    (freeze/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for row in manifest['files']:assert sha(freeze/row['path'])==row['sha256']
    print(json.dumps(dict(result=r['result'],clips=8,C_H=audit['indexed_C_H_unchanged'],freeze_files=len(manifest['files']))))
except Exception as exc:
    r.update(result='failed',error=repr(exc))
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise
