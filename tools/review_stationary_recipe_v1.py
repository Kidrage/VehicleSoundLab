"""Publish same-gain actual C candidates and explicit driving telemetry."""
import argparse,csv,json,os,shutil,sys,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','drive','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',clips=[],inputs={})
files={};roots={};traces={}


def clip(key,path):
    r['inputs'][str(path)]=sha(path);wave,rate=sf.read(path,always_2d=True);assert rate==48000 and wave.shape[1]==2
    wave=wave*.5;fade=np.sin(np.linspace(0,np.pi/2,240))**2
    wave[:240]*=fade[:,None];wave[-240:]*=fade[::-1,None]
    dest=a.out/(key+'.wav');sf.write(dest,wave,48000,subtype='PCM_24')
    actual,rate=sf.read(dest,always_2d=True);assert np.max(abs(actual-wave))<=2**-23 and abs(actual).max()<.95
    url='http://127.0.0.1:8789/'+dest.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.status==200 and response.read()==dest.read_bytes()
    files[key]=dest.name;r['clips'].append(dict(key=key,file=dest.name,frames=len(actual),sha256=sha(dest)))


try:
    fit=load(a.fit/'report.json');drive=load(a.drive/'report.json');assert fit['result']=='four_stationary_candidates_rendered' and drive['result']=='passed'
    for path in [a.fit/'report.json',a.drive/'report.json']:r['inputs'][str(path)]=sha(path)
    template=repo/'tools/stationary_recipe_v1/review.html';shutil.copy2(__file__,a.out/'executed_review.py');shutil.copy2(template,a.out/'executed_review.html')
    fig,axes=plt.subplots(3,1,figsize=(10,9),layout='constrained')
    for i,row in enumerate(fit['anchors'][1:],1):
        k=str(i);folder=a.fit/row['name'];roots[k]=row['root_hz']
        clip(k+'_original_mix',folder/'original.wav');clip(k+'_reference_mix',folder/'reference.wav')
        for render in row['renders']:
            seed=render['seed'];clip(k+f'_candidate_mix_{seed}',folder/f'candidate_{seed}.wav');clip(k+f'_candidate_detail_{seed}',folder/f'detail_{seed}.wav')
        for label,path in [('Source',folder/'reference.wav'),('Original DNA',folder/'original.wav'),('Resonant35',folder/'candidate_8121907.wav')]:
            wave,rate=sf.read(path,always_2d=True)
            if label!='Source':wave=wave[24000:]
            hz,power=signal.welch(wave[:,0],fs=48000,nperseg=2048,noverlap=1536,detrend=False)
            axes[i-1].plot(hz,10*np.log10(power+1e-30),label=label,lw=.8)
        axes[i-1].set(xscale='log',xlim=(800,9000),ylim=(-130,-30),title=row['name']+' | left channel; no level matching',xlabel='Hz',ylabel='PSD dBFS/Hz')
        axes[i-1].legend(fontsize=8);axes[i-1].grid(alpha=.2)
    fig.savefig(a.out/'spectra.png',dpi=140);plt.close(fig)
    for scenario in ['neutral','shifts']:
        for label,variant in [('original',0),('candidate',2)]:
            prefix=a.drive/f'{scenario}_{variant}_2_240'
            clip(scenario+'_'+label+'_mix',prefix.with_suffix('.wav'))
            if variant:clip(scenario+'_candidate_detail',prefix.with_name(prefix.name+'_detail.wav'))
        path=a.drive/(scenario+'_2_2_240.csv');r['inputs'][str(path)]=sha(path)
        with path.open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
        traces[scenario]=[{k:(int(row[k]) if k in ['gear','lifecycle','operating'] else float(row[k])) for k in ['rpm','gear','lifecycle','operating','detail_support']} for row in rows]
    data=dict(files=files,roots=roots,traces=traces)
    page=template.read_text(encoding='utf-8').replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')))
    assert page.count('<audio ')==1 and '__DATA__' not in page
    (a.out/'index.html').write_text(page,encoding='utf-8',newline='\n')
    (a.out/'player.js').write_text(page.split('<script>')[1].split('</script>')[0],encoding='utf-8',newline='\n')
    url='http://127.0.0.1:8789/'+(a.out/'index.html').relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=20) as response:assert response.status==200 and response.read()==(a.out/'index.html').read_bytes()
    r.update(result='passed',url=url,clip_count=len(files),common_gain=.5,single_player=True,low_anchor_not_promoted=True,
             human_accepted=False,native_UI_changed=False,interactive_browser_verified=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
