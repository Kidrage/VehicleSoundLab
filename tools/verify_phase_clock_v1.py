"""Independent sweep, stereo, missing-line and reference-phase controls."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path)
parser.add_argument('--method',choices=('short','debiased'),required=True)
parser.add_argument('--tracker',choices=('fft','chirplet','hybrid'),default='fft')
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from phase_clock_v1.fixtures import source, KNOWN_GAIN
from phase_clock_v1.projection import polish as short_polish
from phase_clock_v1.debiased import polish as debiased_polish
polish=short_polish if args.method=='short' else debiased_polish
from shift_evidence_v1.spectrum import observe
from phase_clock_v1.chirplet import observe as chirplet_observe
from phase_clock_v1.tracking import track as hybrid_track
from state_colour_v2.clock import follow
from state_colour_v2.features import select_windows, shape_delta
from state_dna_v1.compare import describe
from exterior_clock_v1.warp import warp

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.phase-clock-controls/1',method=args.method,tracker=args.tracker,curves=[],negative_controls=[],
    limits=['Known coherent stereophonic OSC only; no real load or microphone-phase identification',
            'Reference5 paths must exist before refinement; missing dense paths are not repaired'])


def measure(audio,times,roots,span,falling):
    _,_,evidence,z=describe(audio,0,times,roots,*span,phase_refiner=polish)
    selected=select_windows(evidence,not falling)
    if not selected.any():raise ValueError('No selected root45..50Hz window')
    power=np.mean(abs(z[selected])**2,axis=0)
    phase=np.angle(np.mean(z[selected,:,0]*np.conj(z[selected,:,1]),axis=0))
    return power,phase,evidence


for curve in ('linear','exponential','rapid_curve','rapid_corner'):
    result=dict(curve=curve,cases=[]);powers={}
    for falling in (False,True):
        for noise in (False,True):
            audio,times,roots,span,z=source(curve,falling,noise=noise)
            if args.tracker=='hybrid':
                tracking,tracking_evidence=hybrid_track(audio,0,*span,float(np.interp(span[0],times,roots)),5)
            else:
                s=observe(audio,0,80,hop=240) if args.tracker=='fft' else chirplet_observe(audio)
                tracking=follow(s['hz'],s['seconds'],s['power_low'],*span,float(np.interp(span[0],times,roots)),5)
                tracking_evidence=dict(selected=args.tracker)
            if not tracking['rows']:
                result['cases'].append(dict(falling=falling,noise=noise,status=tracking['status']));continue
            at=np.array([r['seconds'] for r in tracking['rows']]);hz=np.array([r['root_hz'] for r in tracking['rows']])
            observed_span=[max(span[0],float(at[0])),min(span[1],float(at[-1]))]
            try:
                measured,phase,evidence=measure(audio,at,hz,observed_span,falling)
                truth,truth_phase,_=measure(audio,times,roots,observed_span,falling)
            except ValueError as exc:
                result['cases'].append(dict(falling=falling,noise=noise,status='measurement_rejected',reason=str(exc)));continue
            error=shape_delta(truth,measured).mean(axis=1)
            phase_error=np.angle(np.exp(1j*(phase-truth_phase)))
            ideal_phase_error=np.angle(np.exp(1j*(phase-np.angle(z[:,0]*np.conj(z[:,1])))))
            row=dict(falling=falling,noise=noise,status='measured',tracking=tracking_evidence,shape_error_db=error.tolist(),
                stereo_phase_error_radians=[float(phase_error[h-1]) for h in (3,5,7,10,15)],
                ideal_clean_phase_error_radians=None if noise else [float(ideal_phase_error[h-1]) for h in (3,5,7,10,15)],
                agreement=evidence['correction']['independent_agreement'],selected=evidence['windows'])
            result['cases'].append(row);powers[falling,noise]=measured
            if not falling and not noise:
                changed,*_=source(curve,gain=KNOWN_GAIN)
                changed_power,_,_=measure(changed,at,hz,observed_span,False)
                powers['known']=changed_power
    if (False,False) in powers and (True,False) in powers:
        result['zero_shape_error_db']=shape_delta(powers[True,False],powers[False,False]).mean(axis=1).tolist()
        ideal=shape_delta(abs(z)**2,abs(z*KNOWN_GAIN[:,None])**2).mean(axis=1)
        known=shape_delta(powers[True,False],powers['known']).mean(axis=1)
        result['known_shape_error_db']=(known-ideal).tolist()
    report['curves'].append(result)
    (args.out/(curve+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(curve,[(c['status'],round(float(max(abs(np.array(c.get('shape_error_db',[999]))))),3)) for c in result['cases']],flush=True)

for name,config in [('missing_reference',dict(missing=True)),('reference_phase_only',dict(contaminated=True))]:
    audio,times,roots,span,_=source('linear',**config)
    initial,where,e=warp(audio,0,times,roots,*span)
    try:
        _,_,result=polish(audio,0,initial,where,5,e['source_cutoff_hz'])
        rejected=not result['independent_agreement']['passed']
        row=dict(name=name,rejected=rejected,agreement=result['independent_agreement'],diagnostics=result['diagnostics'])
    except ValueError as exc:row=dict(name=name,rejected=True,reason=str(exc))
    report['negative_controls'].append(row);print(name,row['rejected'],flush=True)
    if name=='missing_reference':
        if args.tracker=='hybrid':track,_=hybrid_track(audio,0,*span,float(np.interp(span[0],times,roots)),5)
        else:
            s=observe(audio,0,80,hop=240) if args.tracker=='fft' else chirplet_observe(audio)
            track=follow(s['hz'],s['seconds'],s['power_low'],*span,float(np.interp(span[0],times,roots)),5)
        report['negative_controls'].append(dict(name='missing_reference_coarse_path',rejected=not bool(track['rows']),status=track['status']))

# The default shared measurement path must remain identical to its frozen source.
old_path=args.workspace/'baselines/state_colour_v2/evidence/colour_attempt1/source/tools/state_dna_v1/compare.py'
spec=importlib.util.spec_from_file_location('frozen_compare',old_path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
audio,times,roots,span,_=source('linear')
a=old.describe(audio,0,times,roots,*span);b=describe(audio,0,times,roots,*span)
report['default_path_identical']=all(np.array_equal(a[i],b[i]) for i in (0,1,3)) and a[2]==b[2]
cases=[c for r in report['curves'] for c in r['cases']]
measured=[c for c in cases if c['status']=='measured']
report['measured_cases']=len(measured)
report['coarse_rejected_cases']=len(cases)-len(measured)
report['maximum_phase_shape_error_db']=float(max(max(abs(np.array(c['shape_error_db']))) for c in measured))
report['maximum_stereo_phase_error_radians']=float(max(max(abs(np.array(c['stereo_phase_error_radians']))) for c in measured))
report['maximum_clean_ideal_phase_error_radians']=float(max(max(abs(np.array(c['ideal_clean_phase_error_radians']))) for c in measured if not c['noise']))
report['maximum_known_shape_error_db']=float(max(max(abs(np.array(r['known_shape_error_db']))) for r in report['curves'] if 'known_shape_error_db' in r))
report['result']='pass' if (len(cases)==16 and all(c['status']=='measured' and c['agreement']['passed'] for c in cases) and
    report['maximum_phase_shape_error_db']<.5 and report['maximum_known_shape_error_db']<.5 and
    report['maximum_stereo_phase_error_radians']<.02 and report['maximum_clean_ideal_phase_error_radians']<.02 and all(c['rejected'] for c in report['negative_controls']) and
    report['default_path_identical']) else 'fail'
report['conditional_refinement_passed']=bool(measured and report['maximum_phase_shape_error_db']<.5 and
    report['maximum_known_shape_error_db']<.5 and report['maximum_stereo_phase_error_radians']<.02 and
    all(c['agreement']['passed'] for c in measured) and all(c['rejected'] for c in report['negative_controls']))
repo=Path(__file__).resolve().parents[1]
paths=[Path(__file__),*sorted((repo/'tools/phase_clock_v1').glob('*.py')),repo/'tools/state_dna_v1/compare.py',repo/'tools/exterior_clock_v1/warp.py',repo/'tools/state_colour_v2/clock.py',repo/'tools/state_colour_v2/features.py',repo/'tools/sound_dna/windowed.py',repo/'tools/shift_evidence_v1/spectrum.py']
report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in paths}
(args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:v for k,v in report.items() if k.startswith('maximum') or k in ('result','default_path_identical')}))
sys.exit(report['result']!='pass')
