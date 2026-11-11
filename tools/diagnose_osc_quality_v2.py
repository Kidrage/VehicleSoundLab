"""Isolate sparse information loss from sinusoidal representation capacity."""
from runtime_review import ROOT,sha
import json
import subprocess
import numpy as np
import soundfile as sf
from osc_quality_v2.bank import fit,render,export
from osc_quality_v2.render import variant
from reference_segments import checked_source

OUT=ROOT/'references/analysis/osc_quality_v2'
PROBE=ROOT/'build-osc-density-v1/Release/dense_osc_probe.exe'


def main():
    OUT.mkdir(exist_ok=False)
    source=checked_source('A')
    parent=ROOT/'references/analysis/osc_quality_v1'
    prior=json.loads((parent/'results.json').read_text(encoding='utf-8'))
    # All methods start from the already-published identical bandwidth control.
    # It has the same audition gain and ramps; no extra HF or loudness matching.
    path=parent/'band_only_audition.wav'
    assert sha(path)==prior['audition']['files']['band_only']['sha256']
    x,rate=sf.read(path)
    report=dict(schema='vsl.osc-quality/2',source=source,input=str(path.relative_to(ROOT)),input_sha256=sha(path),
        purpose='Representation-completeness diagnosis after user rejected short-joint quality1; not a general engine voice.',
        previous_candidate='Rejected: original low-quality/compressed texture basically unchanged.',
        native_application_changed=False,high_tuning_deferred=True,variants={},controls={},probe_sha256=sha(PROBE))
    for name,limit in [('complete',None),('rank64',64),('rank16',16)]:
        report['variants'][name]=variant(PROBE,OUT,x,rate,name,limit)
        print(name,report['variants'][name]['residual_db'],flush=True)
    # A known off-bin AM/chirp checks edges, sign, overlap normalization, and C
    # recurrence independently from any subjective engine interpretation.
    t=np.arange(4096)/rate
    control=(.2+.1*np.cos(2*np.pi*25*t))*np.cos(2*np.pi*(221.7*t+70*t*t)+.4)
    model=OUT/'control.model';export(model,fit(control),rate,len(control))
    target=OUT/'control_c_float.wav'
    subprocess.run([str(PROBE),str(model),str(target)],check=True,capture_output=True,timeout=20)
    c,sr=sf.read(target,always_2d=True)
    error=float(abs(c[:,0]-control).max());assert sr==rate and error<1e-7
    report['controls']['known_AM_chirp']=dict(max_error=error,including_edges=True)
    # Loader must reject truncation and invalid oscillator bins without output.
    for name,text in [('truncated',model.read_text().splitlines()[0]+'\n'),
        ('invalid_bin','VSL_DENSE_OSC 1 48000 128 512 128 1\n-384 1\n999 1 0\n')]:
        invalid=OUT/f'{name}.model';invalid.write_text(text,encoding='ascii')
        result=subprocess.run([str(PROBE),str(invalid),str(OUT/f'{name}.wav')],capture_output=True,timeout=10)
        assert result.returncode!=0 and not (OUT/f'{name}.wav').exists()
        report['controls'][name]='rejected'
    (OUT/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main()
