import sys
import subprocess
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
from analyze_audio import read_pcm,measure
import numpy as np
clips=[('B_cabin_steady',84,10),('B_cabin_pull',218,12),('B_cabin_load_release',475,10)]
catalog=[]
for name,start,duration in clips:
    path=ROOT/'references/clean'/(name+'.wav')
    if not path.exists():
        subprocess.run([sys.executable,str(ROOT/'tools/prepare_reference.py'),str(ROOT/'references/approval_manifest.json'),
            'B',str(ROOT/'references/raw/B_local_Tecnica_binaural.mp3'),str(path),
            '--start',str(start),'--duration',str(duration),'--highpass'],check=True)
    x,sr,total=read_pcm(path,0,duration)
    m=measure(x,sr)
    m.update(left=measure(x[:,:1],sr),right=measure(x[:,1:],sr),
        correlation=float(np.corrcoef(x.T)[0,1]),
        context='B user-provided binaural POV source; stereo preserved. Motion labels inferred from spectral changes, not CAN.')
    path.with_suffix('.analysis.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    catalog.append(dict(name=name,start=start,duration=duration,file=str(path),metrics=m))
    print(name,'centroid',round(m['centroid_hz'],1),'rms',round(m['rms_dbfs'],2),'correlation',round(m['correlation'],3))
(ROOT/'references/analysis/B_clip_catalog.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
