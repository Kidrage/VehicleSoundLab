"""Freeze the pre-integration renderer and observe early-startup spectral motion."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from residual_osc_v1.spectrum import matrices
a.out.mkdir(parents=True,exist_ok=False);(a.out/'bin').mkdir()
r=dict(result='running',source_sha256=sha(__file__),physical_timing_identified=False)
shutil.copy2(__file__,a.out/'executed_prepare.py')
try:
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=repo).strip()
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    assert len(rows)==454
    for row in rows:assert sha(repo/row['文件'])==row['SHA-256']
    shutil.copy2(repo/'handoff/C文件索引.csv',a.out/'C文件索引.csv')
    r['C_H_sha256']={row['文件']:row['SHA-256'] for row in rows}
    r['commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    subprocess.run(['git','archive','--format=zip','--output='+str(a.out/'source.zip'),r['commit']],cwd=repo,check=True)
    for name in ['VslAtlasMonitor.exe','VslAtlasDrive_probe.exe','VslAtlasTake_render.exe']:
        source=repo/'build-stereo-bed-v1/bin/Release'/name
        shutil.copy2(source,a.out/'bin'/name)
    r['binary_sha256']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    old=json.loads((a.workspace/'references/analysis/stereo_bed_v1/verification1/report.json').read_text(encoding='utf-8'))
    assert old['result']=='technical_pass_only'
    r['legacy_reference']=str(a.workspace/'references/analysis/stereo_bed_v1/verification1')
    r['legacy_reference_report_sha256']=sha(Path(r['legacy_reference'])/'report.json')
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation');r['input']=meta
    segment=x[round((36.65-33)*48000):round((37.12-33)*48000)]
    edges=[300,400,520,660,800,960,1140,1340,1560,1820,2120,2500,3000,3700,4600,6000,8000]
    bands=list(zip(edges[:-1],edges[1:]))
    # Two broad spectral endpoints. Quarter observations expose within-endpoint variation.
    halves=[matrices(v,bands) for v in np.array_split(segment,2)]
    quarters=[matrices(v,bands) for v in np.array_split(segment,4)]
    r['half_moments']=halves;r['quarter_moments']=quarters;r['seconds']=[36.65,37.12]
    f,t,z=signal.stft(segment,48000,nperseg=4096,noverlap=3856,axis=0,boundary=None,padded=False)
    psd=np.mean(abs(z)**2,axis=1)
    selected=(f>=600)&(f<=2400)
    peak=f[selected][np.argmax(psd[selected],axis=0)]
    r['dominant_peak_hz']=peak.tolist();r['dominant_peak_times']=(36.65+t).tolist()
    r['ridge_interpretation']='Dominant mixed-recording peaks only; switches between lines do not prove a single accelerating motor/rpm clock.'
    fig,ax=plt.subplots(figsize=(11,4),constrained_layout=True)
    ax.pcolormesh(36.65+t,f,10*np.log10(np.maximum(psd,1e-20)),shading='auto',vmin=-60,vmax=-18)
    ax.plot(36.65+t,peak,'w.',markersize=3)
    ax.set(ylim=(300,3000),xlabel='Decoded audio seconds',ylabel='Acoustic Hz',title='Early-startup spectral motion; white dots are maxima, not a motor clock')
    fig.savefig(a.out/'early_motion.png',dpi=140);plt.close(fig)
    r.update(result='before_and_motion_observations_frozen',mapping='Linear normalized CRANK progress is an engineering preview, not measured physical duration')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],commit=r['commit'],C_H=len(rows),peak_range=[float(peak.min()),float(peak.max())])))
