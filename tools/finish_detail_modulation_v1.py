"""Add the high-detail ablation requested after the initial diagnosis began."""
from runtime_review import ROOT,sha
import json
import numpy as np
import soundfile as sf

OUT=ROOT/'references/analysis/detail_modulation_v1'


def main():
    out=OUT/'listening';out.mkdir(exist_ok=False);files={}
    for name in ['detail075_radial','detail100_radial']:
        x,rate=sf.read(OUT/f'{name}_float.wav',always_2d=True);x=x[:384000]*.5
        x[:240]*=np.linspace(0,1,240)[:,None];x[-240:]*=np.linspace(1,0,240)[:,None]
        path=out/f'{name}_audition.wav';sf.write(path,x,rate,subtype='PCM_24')
        files[name]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path),gain=.5,frames=len(x))
    result=dict(user_feedback='停在某个数值后仍持续；大概70%以上，越高越明显',
        source_clock_unchanged=True,no_branch_at70=True,
        interpretation='Intended complex AM/PM remains active at a stationary knob. Its strength increases continuously; observed threshold is a listening threshold, not a coded70% switch. Excessive phase motion is a voicing/control-design concern, not found pitch-control crosstalk.',
        causal_limit='Phase-fixed ablation preserves per-harmonic/channel magnitude but also removes temporal interchannel phase variation. It is diagnostic and may sound flatter; subjective cause is pending.',
        auditions=files,accepted_native_modified=False)
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
