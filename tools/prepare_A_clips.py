import subprocess
import sys
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
from profile_reference import coverage
from analyze_audio import read_pcm,measure
import soundfile as sf
clips=[
    ('A_corsa_tailpipe_idle',208,5,'Corsa; camera at tailpipe; microphone position not independently verified'),
    ('A_corsa_tailpipe_blips',238,10,'Corsa; low rear/near tailpipe camera; transient rev sequence'),
    ('A_tailpipe_road_pull',313.5,6,'Road sequence; tailpipe camera; source edit boundaries need listening review'),
    ('A_engine_bay_texture',270,7,'Engine bay camera; structural/noise comparison only')]
catalog=[]
for name,start,duration,context in clips:
    out=ROOT/'references/clean'/f'{name}.wav'
    if not out.exists():
        subprocess.run([sys.executable,str(ROOT/'tools/prepare_reference.py'),str(ROOT/'references/approval_manifest.json'),
            'A',str(ROOT/'references/raw/A_7aZm1Wkp6QM.webm'),str(out),'--start',str(start),'--duration',str(duration),'--highpass'],check=True)
    x,sr,total=read_pcm(out,0,duration)
    result=measure(x,sr)
    result.update(source_start_seconds=start,context=context,
        peak_lobe_energy_coverage=coverage(x.mean(axis=1),sr),
        coverage_warning='Optimistic STFT main-lobe energy bound, NOT oscillator-resynthesis accuracy or perceptual similarity.')
    out.with_suffix('.analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    catalog.append(dict(name=name,file=str(out),start=start,duration=duration,context=context,metrics=result))
(ROOT/'references/analysis/A_clip_catalog.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
for c in catalog:
    m=c['metrics'];print(c['name'],json.dumps({k:m[k] for k in ('peak_dbfs','rms_dbfs','centroid_hz','spectral_flatness','clipped_sample_fraction','peak_lobe_energy_coverage')},indent=2))
