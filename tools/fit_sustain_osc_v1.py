"""Train a finite statistical profile for a genuinely new sustained source."""
from runtime_review import ROOT,sha
import json
import numpy as np
import soundfile as sf
from reference_segments import read_segment
from sustain_osc_v1.observation import ridge,normalize
from sustain_osc_v1.profile import estimate,export

OUT=ROOT/'references/analysis/sustain_osc_v1'


def main():
    OUT.mkdir(exist_ok=False)
    x,rate,provenance=read_segment('A_exterior_moving','exterior_dynamic_observation')
    seconds=np.arange(.10,1.25001,.005)
    paths={str(n):ridge(x,rate,seconds,n/1000) for n in (80,128,192)}
    spread=float(np.max(np.ptp(np.asarray(list(paths.values())),axis=0)))
    assert spread<2,'Relative frequency estimates disagree; stop before fitting'
    assert np.max(abs(np.diff(paths['128'])))<1,'Ridge discontinuity; no silent repair'
    y,warp=normalize(x,rate,seconds,paths['128'])
    model,stats=estimate(y)
    export(OUT/'voice.model',model,rate)
    np.savez(OUT/'profile_arrays.npz',**model)
    np.savez(OUT/'ridge_observations.npz',seconds=seconds,**{f'window{k}':v for k,v in paths.items()})
    sf.write(OUT/'normalized_reference_float.wav',y,rate,subtype='FLOAT')
    report=dict(schema='vsl.sustain-osc/1',source=provenance,
        training_source_seconds=[316.10,317.25],channels='L/R microphone observations; no engine-bank assignment',
        ridge_window_max_spread_hz=spread,warp=warp,statistics=stats,model_sha256=sha(OUT/'voice.model'),
        status='Experimental stationary relative-pitch profile, not measured RPM/load/state calibration.')
    (OUT/'fit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
