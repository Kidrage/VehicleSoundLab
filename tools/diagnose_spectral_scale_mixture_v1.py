"""Known two-layer counterexample, with no real recording access."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from low_peak_selection_v1.scale import feature,compare
from drive_evidence_v1.sources import sha

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},real_source_read=False)
try:
    plan=load(repo/'research/low_spectral_scale_v1_plan.json')
    for path in [Path(__file__),repo/'research/spectral_scale_mixture_v1_plan.json',
        repo/'research/low_spectral_scale_v1_plan.json',repo/'tools/low_peak_selection_v1/scale.py',
        repo/'tools/accel_material_v1/features.py',repo/'tools/idle_material_v1/features.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    t=np.arange(24000)/48000;orders=np.arange(3,451);ratio=2**(128/1536)
    def moving(q):
        left=sum(.07*float(n)**-.65*np.cos(2*np.pi*10.613*n*q*t+.173*n) for n in orders)
        return np.column_stack((left,.67*left))
    first,second=moving(1.),moving(ratio)
    frequencies=np.arange(1107.3,5000.,37.137)
    left=sum(.04*np.cos(2*np.pi*f*t+.37*k) for k,f in enumerate(frequencies))
    fixed=np.column_stack((left,.67*left));mixture_a=first+fixed;mixture_b=second+fixed
    fa,_=feature(first,plan);fb,_=feature(second,plan);moving_match=compare(fa,fb,plan)
    r['moving_match']=moving_match
    assert moving_match['supported'] and abs(moving_match['global_match']['shift_bins']-128)<=8
    fa,_=feature(mixture_a,plan);fb,_=feature(mixture_b,plan);mixed_match=compare(fa,fb,plan)
    r['mixed_match']=mixed_match
    np.savez_compressed(a.out/'known_layers.npz',moving_reference=first,moving_current=second,
        fixed=fixed,mixture_reference=mixture_a,mixture_current=mixture_b)
    assert not mixed_match['supported'],mixed_match
    error=max(float(abs((mixture_a-first)-fixed).max()),float(abs((mixture_b-second)-fixed).max()))
    assert error<1e-14
    r.update(result='known_moving_layer_with_fixed_layer_rejects_whole_scale_rule',
        linear_mixture_error=error,ratio=ratio,fixed_layer_lines=len(frequencies),real_source_read=False,
        conclusion='Whole-spectrum scale rejection does not disprove a correctly moving tonal sublayer. No real A source separation inferred.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],moving_shift=r['moving_match']['global_match']['shift_bins'],
    mixed_shift=r['mixed_match']['global_match']['shift_bins'],mixed_band_shifts=[q['shift_bins'] for q in r['mixed_match']['band_matches']])),flush=True)
