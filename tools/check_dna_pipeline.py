import sys
from pathlib import Path
import subprocess
import wave
import json
import argparse
import hashlib
import re
sys.path.insert(0,str(Path(__file__).resolve().parent/'python_deps'))
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--renderer',type=Path,default=ROOT/'build-v07/Release/vsl_render.exe')
parser.add_argument('--out',type=Path,default=ROOT/'renders')
args=parser.parse_args()
folder=args.out;folder.mkdir(parents=True,exist_ok=True)
sr=48000;t=np.arange(sr*2)/sr
x=.2*np.cos(2*np.pi*220*t+.3)+.08*np.cos(2*np.pi*440*t-.7)+.03*np.cos(2*np.pi*660*t+.9)
source=folder/'known_steady_harmonics.wav'
with wave.open(str(source),'wb') as f:
    f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr);f.writeframes((x*32767).astype('<i2').tobytes())
dna=folder/'known_steady_harmonics.dna'
subprocess.run([sys.executable,str(ROOT/'tools/analyze_audio.py'),str(source),'--start','.25','--duration','1',
    '--root-hz','220','--export-dna',str(dna)],check=True,capture_output=True)
output=folder/'DNA_中文路径验证.wav'
rendered=subprocess.run([str(args.renderer),str(output),'--profile','3','--rpm','3000',
    '--pure','--dna',str(dna),'--seconds','4'],check=True,capture_output=True)
with wave.open(str(output),'rb') as f:
    # Continuous lifecycle (V010+) needs time to finish catch/settle. Observe
    # only the stable bench pitch and exclude the offline endpoint fade.
    y=np.frombuffer(f.readframes(f.getnframes()),'<i2').reshape(-1,2)[2*sr:-sr//20,0].astype(float)/32768
freq=np.fft.rfftfreq(len(y),1/sr);power=np.abs(np.fft.rfft(y*np.hanning(len(y))))**2
dominant=float(freq[np.argmax(power)])
assert abs(dominant-220)<1
for hz in (220,440,660):assert power[np.argmin(abs(freq-hz))]>power.max()*.005
metrics=json.loads(source.with_suffix('.analysis.json').read_text())
assert metrics['dna']['fit_residual_to_signal_db']<-60
report=dict(result='pass',dominant_hz=dominant,fit_residual_db=metrics['dna']['fit_residual_to_signal_db'],
    dsp_version=re.search(r'DSP ([0-9.]+)',rendered.stdout.decode()).group(1),renderer_sha256=hashlib.sha256(args.renderer.read_bytes()).hexdigest(),
    pipeline='Known steady harmonic WAV -> fitted .dna -> C oscillator runtime -> PCM WAV',unicode_path=True,
    rendered_seconds=4,analysis_interval_seconds=[2,3.95],
    limitation='Verifies the interchange, not a Serum patch or a measured engine model.')
(folder/'dna_pipeline_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
