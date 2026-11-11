"""Cross-voice engineering fixtures, clearly separated from real-car validation."""
from runtime_review import ROOT,sha
from sound_dna.profile import compile_file
import json
import shutil
import numpy as np
import soundfile as sf


def main():
    out=ROOT/'references/analysis/sound_dna_v1';out.mkdir(exist_ok=False)
    bank=ROOT/'voices/dna_bank_v1';bank.mkdir(parents=True,exist_ok=False);index=[]
    original=ROOT/'references/analysis/sustain_osc_v1/voice.model'
    assert sha(original)=='6f8992e6674f603334f82bdbc526fd8ac5bbe750606154c5e83c166c077bb1b7'
    shutil.copy2(original,bank/'V10 Exterior.model')
    index.append(dict(name='V10 Exterior',file='V10 Exterior.model',model_sha256=sha(original),kind='Approved recording-derived mixed exterior context; fixed-phase listening accepted',base_hz=46.875,source='A316.10..317.25; not measured RPM'))
    for name,root,harmonics,kind in [('Warm Additive',110.,48,'warm'),('Hollow Spectrum',164.0625,64,'hollow')]:
        rate=44100 if kind=='warm' else 48000;t=np.arange(rate*3)/rate;x=np.zeros((len(t),2))
        selected=list(range(1,25)) if kind=='warm' else [2,5,8,13,21,34,55]
        for h in selected:
            a=.16/h**1.25 if kind=='warm' else .11/(1+.05*h)
            phase=.19*h if kind=='warm' else .47*h
            mod=1+.12*np.sin(2*np.pi*.7*t)+.05*np.sin(2*np.pi*(1.3+.015*h)*t+.3*h)
            for c in range(2):x[:,c]+=a*(1-.07*c)*mod*np.cos(2*np.pi*root*h*t+phase+c*.06*h)
        assert abs(x).max()<.8
        source=out/f'{kind}_known_source.wav';sf.write(source,x,rate,subtype='FLOAT')
        build=compile_file(source,out/kind,root,name,harmonics,8)
        shutil.copy2(out/kind/'voice.model',bank/f'{name}.model')
        index.append(dict(name=name,file=f'{name}.model',model_sha256=build['model_sha256'],base_hz=root,kind='Analytic additive engineering fixture, not a real engine or user Serum patch',build=str((out/kind/'build.json').relative_to(ROOT))))
    result=dict(schema='vsl.dna-bank/1',voices=index,shared_renderer='modules/sound_dna',low_body_and_noise='Excluded',goal_complete=False)
    (bank/'index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
