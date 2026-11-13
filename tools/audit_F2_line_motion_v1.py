"""Audit local moments by rectangular-DTFT identities and independent bisection."""
import argparse
import importlib.util
import importlib
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.controls import controls
from line_motion_v1.center import centered


def load(path):return json.loads(path.read_text(encoding='utf-8'))
def same(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif isinstance(a,float):assert abs(a-b)<1e-10
    else:assert a==b


def independent_moments(x,f):
    # Rectangle sums shifted by the Hann Fourier coefficients, no window helper.
    n=np.arange(len(x),dtype=float)/48000
    values=[np.sum(x*np.exp(-2j*np.pi*hz*n)) for hz in (f,f-1,f+1)]
    c=.5*values[0]-.25*(values[1]+values[2])
    d=np.pi/(2j)*(values[1]-values[2])
    return c,d


def offset(x,f):
    c,d=independent_moments(x,f)
    return float(-np.imag(d/c)/(2*np.pi))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-line-motion-audit/1',result='running',sources={},real_audio_read=False,
    phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_line_motion_v1'
    first,second=[load(root/n/'report.json') for n in ('observe1','observe2')]
    assert first['result']=='failed' and not first['real_audio_read'] and not first['controls']['passed']
    assert second['controls']['passed'] and second['method']=='center'
    snapshot=root/'observe1/exact_sources/tools/line_motion_v1'
    spec=importlib.util.spec_from_file_location('frozen_line_motion',snapshot/'__init__.py',submodule_search_locations=[str(snapshot)])
    package=importlib.util.module_from_spec(spec);sys.modules[spec.name]=package;spec.loader.exec_module(package)
    original=importlib.import_module('frozen_line_motion.controls').controls()
    same(original,first['controls'])
    same(controls(observer=centered),second['controls'])
    arrays=np.load(root/'observe2/observations.npz')
    assert sha(root/'observe2/observations.npz')==second['arrays_sha256']
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation')
    report['real_audio_read']=True
    assert np.array_equal(audio,arrays['audio']) and provenance==second['provenance']
    errors=dict(moment_relative=0.,derivative_relative=0.,endpoint_Hz=0.,initial_Hz=0.,root_Hz=0.,root_residual_Hz=0.)
    counts=dict(observations=0,resolved=0,unresolved=0,anchor_complete_rows=0)
    qualified=[]
    for index,row in enumerate(second['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        measured=row['measured']
        resolved=np.array(measured['root_resolved']);nominal=row['nominal_Hz']
        assert np.array_equal(resolved,arrays['root_resolved'][index])
        for line,f in enumerate(nominal):
            for channel in range(2):
                x=part[:,channel];c,d=independent_moments(x,f)
                errors['moment_relative']=max(errors['moment_relative'],abs(c-arrays['moment'][index,line,channel])/max(1,abs(c)))
                errors['derivative_relative']=max(errors['derivative_relative'],abs(d-arrays['derivative_moment'][index,line,channel])/max(1,abs(d)))
                raw=f-np.imag(d/c)/(2*np.pi)
                errors['initial_Hz']=max(errors['initial_Hz'],abs(raw-measured['initial_frequency_Hz'][line][channel]))
                lo,hi=f-.5,f+.5;left,right=offset(x,lo),offset(x,hi)
                errors['endpoint_Hz']=max(errors['endpoint_Hz'],float(abs(np.array([left,right])-measured['endpoint_offsets_Hz'][line][channel]).max()))
                should=left*right<=0
                assert should==bool(resolved[line,channel])
                if should:
                    a,b=lo,hi
                    for _ in range(40):
                        middle=(a+b)/2
                        if left*offset(x,middle)>0:a=middle
                        else:b=middle
                    local=(a+b)/2
                    observed=measured['frequency_Hz'][line][channel]
                    errors['root_Hz']=max(errors['root_Hz'],abs(local-observed))
                    errors['root_residual_Hz']=max(errors['root_residual_Hz'],abs(offset(x,observed)-measured['root_residual_Hz'][line][channel]))
                    counts['resolved']+=1
                else:
                    assert measured['frequency_Hz'][line][channel]==measured['initial_frequency_Hz'][line][channel]
                    assert measured['root_iterations'][line][channel]==0
                    counts['unresolved']+=1
                counts['observations']+=1
        frequency=np.array(measured['frequency_Hz']);bases=frequency[:3]/np.array([2,3,5])[:,None]
        mean=bases.sum(axis=0)/3
        loo=np.stack([bases[j]-(bases.sum(axis=0)-bases[j])/2 for j in range(3)])
        saved=row['exploratory_group']
        assert np.max(abs(mean-saved['mean_anchor_base_Hz']))<1e-12
        assert np.max(abs(loo-saved['leave_one_out_base_error_Hz']))<1e-12
        eligible=bool(resolved[:3].all() and np.array(measured['supported'])[:3].all())
        assert eligible==row['all_anchor_roots_resolved']
        if eligible:
            counts['anchor_complete_rows']+=1
            qualified.append(dict(source_seconds=row['source_seconds'],base_Hz=mean.tolist(),
                max_leave_one_out_Hz=float(abs(loo).max()),
                heldout_order1_resolved=bool(resolved[4].all()),
                heldout_order1_error_Hz=(frequency[4]-mean).tolist(),
                extra_11_over_5_resolved=bool(resolved[3].all()),
                extra_11_over_5_error_Hz=(frequency[3]-11/5*mean).tolist()))
    assert counts['observations']==90 and counts['anchor_complete_rows']==3
    assert errors['moment_relative']<1e-10 and errors['derivative_relative']<1e-10
    assert errors['initial_Hz']<1e-9 and errors['endpoint_Hz']<1e-9
    assert errors['root_Hz']<1e-8 and errors['root_residual_Hz']<1e-9
    x=audio[:48000,0];f=75.;t=np.arange(48000)/48000
    scalar=sum(complex(v)*np.exp(-2j*np.pi*f*n/48000) for n,v in enumerate(x*np.sin(np.pi*t)**2))
    scalar_error=abs(scalar-arrays['moment'][0,0,0])/max(1,abs(scalar));assert scalar_error<1e-10
    variants={}
    for name in ('observe1','observe2'):
        value=load(root/name/'report.json')
        for relative,digest in value['sources'].items():
            assert sha(root/name/'exact_sources'/relative)==digest
            if name=='observe2':assert sha(repo/relative)==digest
            variants.setdefault(relative,{})[name]=digest
    for path in (Path(__file__),repo/'tools/drive_evidence_v1/sources.py'):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    report.update(result='F2_initial_AM_failure_and_all90_local_frequency_observations_independently_replayed',
        observe1_report_sha256=sha(root/'observe1/report.json'),observe2_report_sha256=sha(root/'observe2/report.json'),
        original_AM_failure_reproduced=True,center_controls_reproduced=True,original_source_samples_exact=True,
        independent_rectangular_DTFT_errors=errors,scalar_moment_relative_error=scalar_error,
        counts=counts,eligible_anchor_rows=qualified,source_variants=variants,
        complete_continuous_coordinate_established=False,selected_fundamental=None,RPM_inferred=False,
        numerical_root_audit_tolerance_is_not_physical_confidence=True,
        limits=['Six of nine rows do not resolve all3 roots in the fixed original rounding boxes; no promotion/interpolation',
            'Unresolved root residual entries are placeholders, never evidence of a solved root; retained raw reassignment only',
            'Three complete local rows are acoustic family observations, not common phase or physical period qualification',
            '82Hz comparisons using unresolved roots remain raw derivative diagnostics only'])
    print(json.dumps(dict(result=report['result'],counts=counts,errors=errors,eligible=qualified)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
