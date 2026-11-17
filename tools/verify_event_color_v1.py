"""Independent SciPy/old-DLL/material checks for optional noise-only coloration."""
import argparse
from copy import deepcopy
import ctypes as ct
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    from event_authoring.audio import read,sha
    from event_authoring.contract import Profile,ProfileV1,Request,pack_profile,validate
    from event_authoring.native import Renderer,controls
    from event_authoring.model import synth
    from event_authoring.measure import observe,spectrum
    from event_authoring.fit import fit
    from event_authoring.response_fit import EDGES
    from vehicle_controller.native import Bridge,Engine
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    a.output.mkdir(parents=True,exist_ok=False);renderer=Renderer(repo)
    profile=dict(gated=0,duration_seconds=.37,attack_seconds=.003,release_seconds=.025,
        sweep_seconds=.12,level=.8,
        modes=[dict(hz=330.,end_hz=620.,amplitude=.08,phase=.7,decay_seconds=.2)],
        bands=[dict(hz=500.,q=.8,amplitude=.2,attack_seconds=.007,decay_seconds=.18),
               dict(hz=7500.,q=1.2,amplitude=.3,attack_seconds=.003,decay_seconds=.1)])
    known=[]
    for cutoff in (0.,300.,4000.,18000.):
        for gated in (0,1):
            sample=deepcopy(profile);sample.update(gated=gated,noise_lowpass_hz=cutoff)
            macros=controls(dict(seconds=.55,seed=20261116,pitch=1.73,decay=.75,texture=.3,hold_seconds=.19))
            actual,_=renderer.render(sample,'catch',macros)
            reference=synth(sample,seed=macros['seed'],pitch=macros['pitch'],decay=macros['decay'],
                texture=macros['texture'],seconds=macros['seconds'],release_at=macros['hold_seconds'] if gated else None)
            reference=np.pad(reference,(0,len(actual)-len(reference))).astype(np.float32)
            error=float(abs(actual.astype(float)-reference).max());assert error<=1e-7,(cutoff,gated,error)
            assert np.array_equal(actual,renderer.render(sample,'catch',macros)[0])
            known.append(dict(cutoff_hz=cutoff,gated=gated,max_error_FS=error))
    rejected=[]
    for cutoff in (-1.,100.,18001.,float('nan'),float('inf'),True):
        sample=deepcopy(profile);sample['noise_lowpass_hz']=cutoff
        try:validate(sample)
        except ValueError:pass
        else:raise AssertionError(('Python accepted',cutoff))
        if not isinstance(cutoff,bool):
            native=pack_profile(profile);native.noise_lowpass_hz=cutoff
            request=Request(id=1,type=2,priority=100,seed=1,strength=1,pitch=1,decay=1,texture=1)
            audio=np.empty(1000,dtype=np.float32)
            assert renderer.fn(ct.byref(native),ct.byref(request),1000,0xffffffff,audio.ctypes.data_as(ct.POINTER(ct.c_float)))==0
        rejected.append(str(cutoff))
    old_path=repo/'build-event-synth-v1/bin/Release/vsl_event_author_bridge.dll'
    old=ct.CDLL(str(old_path));fn=old.vsl_event_author_render
    fn.argtypes=[ct.POINTER(ProfileV1),ct.POINTER(Request),ct.c_uint,ct.c_uint,ct.POINTER(ct.c_float)];fn.restype=ct.c_int
    legacy=[];material=[]
    for kind,slot in (('crank',1),('catch',2)):
        old_doc=json.loads((data/'references/analysis/event_authoring_v1'/(kind+'2')/'profile.json').read_text(encoding='utf-8'))
        doc=json.loads((data/'references/analysis/startup_timbre_v1'/(kind+'1')/'profile.json').read_text(encoding='utf-8'))
        job=old_doc['source_job'];x,_,_=read(job['source'],*job['seconds']);bg,_,_=read(job['source'],*job['background_seconds'])
        duration=len(x)/48000;observation,arrays=observe(x,bg)
        original,_=fit(observation,arrays,duration,bool(old_doc['parameters']['gated']))
        assert original==old_doc['parameters'] and observation==old_doc['observation']
        for seed in (27431,1,20261116,19088743):
            macros=controls(dict(seconds=duration,hold_seconds=duration,seed=seed))
            actual,_=renderer.render(original,kind,macros);prior=np.zeros_like(actual)
            native=pack_profile(original,ProfileV1)
            request=Request(id=1,type=slot,priority=100,seed=seed,strength=1,pitch=1,decay=1,texture=1)
            release=round(duration*48000) if original['gated'] else 0xffffffff
            assert fn(ct.byref(native),ct.byref(request),len(prior),release,prior.ctypes.data_as(ct.POINTER(ct.c_float)))
            assert np.array_equal(actual,prior),(kind,seed,'legacy')
            legacy.append(dict(kind=kind,seed=seed,old_author_exact=True))
            generated,render=renderer.render(doc['parameters'],kind,macros)
            reference=synth(doc['parameters'],seed=seed,seconds=duration).astype(np.float32)
            error=float(abs(generated.astype(float)-reference).max());assert error<=1e-7,(kind,seed,error)
            frequency,power=spectrum(generated[:,None]);bands=[]
            for target in doc['fit']['source_response_fit']['bands']:
                lo,hi=target['hz'];actual_power=float(power[(frequency>=lo)&(frequency<hi)].sum()*(frequency[1]-frequency[0]))
                db=float(10*np.log10(max(actual_power,1e-30)/max(target['target_power'],1e-30)))
                passed=abs(db)<=3 if target['significant_target'] else actual_power<=max(target['target_power']*2,
                    doc['fit']['source_response_fit']['target_positive_psd_excess_power']*2e-4)
                bands.append(dict(hz=[lo,hi],error_db=db,passed=passed,significant=target['significant_target']))
            material.append(dict(kind=kind,seed=seed,max_error_FS=error,bands=bands,all_band_gates_pass=all(r['passed'] for r in bands)))
    current=Bridge(repo);prior=Bridge(repo,repo/'build-vehicle-source-v5/bin/Release/vsl_source_bridge.dll')
    assert current.abi()==6 and prior.abi()==5 and ct.sizeof(Profile)==704 and ct.sizeof(ProfileV1)==696
    try:
        with Engine(prior,0,{'catch':doc}):pass
    except ValueError:pass
    else:raise AssertionError('Old ABI silently accepted new coloration')
    exact=a.output/'exact_sources';exact.mkdir()
    for folder in ('event_authoring','event_designer'):
        shutil.copytree(repo/'tools'/folder,exact/folder,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(__file__,a.output/'executed_verification.py')
    report=dict(result='passed',known=known,rejected_cutoffs=rejected,legacy_author_exact=legacy,
        material=material,all_material_band_gates_pass=all(r['all_band_gates_pass'] for r in material),
        renderer_sha256=renderer.identity,old_renderer_sha256=sha(old_path),source_bridge_sha256=current.sha256,
        old_source_bridge_sha256=prior.sha256,profile_sizes=[ct.sizeof(ProfileV1),ct.sizeof(Profile)],
        abi=[current.abi(),prior.abi()],old_ABI_refuses_color=True,goal_complete=False,timbre_accepted=False)
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='passed',known=len(known),legacy_exact=len(legacy),material=len(material),
        all_material_band_gates_pass=report['all_material_band_gates_pass'],max_material_error_FS=max(r['max_error_FS'] for r in material))))


if __name__=='__main__':main()
