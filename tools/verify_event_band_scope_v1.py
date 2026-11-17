"""Known HF increment over LF, legacy parity, C preview and persisted scope."""
import argparse
import base64
from copy import deepcopy
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import traceback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ui',action='store_true');a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from author_event import author
    from event_authoring.band_scope import normalize,admission
    from event_authoring.measure import observe,spectrum
    from event_authoring.fit import fit
    from event_authoring.model import synth
    from event_authoring.native import Renderer
    from event_authoring.audio import sha
    from event_designer.workspace import EventWorkspace
    from sound_designer.server import create_server
    repo=Path(__file__).resolve().parents[1]
    report=dict(schema='vsl.event-band-scope-verification/1',goal_complete=False,timbre_accepted=False)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    def check(value,name):
        if not value:raise AssertionError(name)
    def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    def upload(path):return dict(filename=path.name,audio=base64.b64encode(path.read_bytes()).decode())
    def edit(p,**kw):return dict(id=p['id'],name=p['name'],kind=p['kind'],context=p['context'],viewpoint=p['viewpoint'],
        controls=deepcopy(p['controls']),parameters=deepcopy(p['document']['parameters']),analysis_scope=p['analysis_scope'],**kw)
    scope=dict(mode='band',low_hz=6000,high_hz=10000)
    t=np.arange(57600)/48000;age=np.maximum(t-.4,0)
    high=.06*np.exp(-age/.08)*np.sin(2*np.pi*8000*age)*(t>=.4)*(t<1.)
    noise=np.random.default_rng(29161).normal(0,.0003,(len(t),2))
    low=.6*np.sin(2*np.pi*117.1875*t)
    x=np.column_stack((low+high,.9*low-.8*high))+noise
    source=a.output/'known.wav';sf.write(source,x,48000,subtype='FLOAT')
    # Use stored FLOAT values so the direct measurement and actual upload see identical inputs.
    x,_=sf.read(source,always_2d=True)
    clip=x[19200:48000];background=x[:14400]
    full,_=observe(clip,background);scoped,arrays=observe(clip,background,scope)
    check(admission(full)<3 and admission(scoped)>20,'HF transient admitted only by its declared band')
    check(abs(scoped['bands'][0]['decay_seconds']-.08)<.02,'Known 80 ms HF amplitude decay')
    profile,policy=fit(scoped,arrays,.6)
    check(any(abs(m['hz']-8000)<24 for m in profile['modes']),'Known HF mode retained')
    check(all(6000<=m['hz']<10000 for m in profile['modes']),'LF carrier excluded from modes')
    check(policy['level_fit_target_excess_power']==scoped['scoped_excess_mean_square'],'Level fit uses scoped increment')
    y=synth(profile,seconds=.6);f,p=spectrum(y[:,None]);generated=float(p[(f>=6000)&(f<10000)].sum()*(f[1]-f[0]))
    relative=abs(generated/scoped['scoped_excess_mean_square']-1)
    check(relative<1e-10,'Scoped power target is achieved without hidden full-band scaling')
    # A quiet upper band exposed global-only RMS fitting: broad lower SOS tails
    # used to overshoot it by >15 dB in the real A candidate.
    dual=.06*np.exp(-age/.08)*np.sin(2*np.pi*2000*age)+.0015*np.exp(-age/.07)*np.sin(2*np.pi*8000*age)
    dual*=((t>=.4)&(t<1.))
    dual_source=np.column_stack((low+dual,.9*low-.8*dual))+noise
    dual_observation,dual_arrays=observe(dual_source[19200:48000],dual_source[:14400],
        dict(mode='band',low_hz=1200,high_hz=14000))
    dual_profile,dual_policy=fit(dual_observation,dual_arrays,.6)
    check(dual_policy['scope_band_fit_qualified'] and all(abs(b['error_db'])<1 for b in dual_policy['scope_band_fit']),
        'Strong lower / quiet upper HF balance follows actual finite filter response')
    # A genuinely infeasible fixed basis is flagged rather than fitted by gain alone.
    from event_authoring.scoped_fit import calibrate
    impossible=deepcopy(dual_profile)
    impossible['modes']=[dict(hz=2000.,end_hz=2000.,amplitude=.02,phase=0.,decay_seconds=.1)]
    for b in impossible['bands']:b['amplitude']=0.
    impossible['level']=1.
    requested=deepcopy(dual_observation);requested['scoped_excess_mean_square']=.001
    requested['bands'][0]['excess_power']=.00000001;requested['bands'][1]['excess_power']=.001
    _,infeasible=calibrate(impossible,requested,.6)
    check(not infeasible['scope_band_fit_qualified'],'Unachievable band target is refused')
    quiet_lf=np.column_stack((.05*np.sin(2*np.pi*117.1875*t)+high,.045*np.sin(2*np.pi*117.1875*t)-.8*high))+noise
    quieter,_=observe(quiet_lf[19200:48000],quiet_lf[:14400],scope)
    lf_sensitivity=abs(quieter['scoped_excess_mean_square']/scoped['scoped_excess_mean_square']-1)
    check(lf_sensitivity<.002,'Out-of-band LF level does not set HF fit amplitude')
    stationary=np.column_stack((low+.01*np.sin(2*np.pi*8000*t),.9*low+.008*np.sin(2*np.pi*8000*t)))
    no_event,_=observe(stationary[19200:48000],stationary[:14400],scope)
    check(admission(no_event)<3,'Stationary HF carrier is refused')
    invalid=[]
    for value in [dict(mode='band',low_hz=100,high_hz=200),dict(mode='band',low_hz=True,high_hz=10000),
                  dict(mode='band',low_hz=float('nan'),high_hz=10000),dict(mode='band',low_hz=6000,high_hz=15000),
                  dict(mode='full',low_hz=60),dict(mode='unknown')]:
        try:normalize(value)
        except ValueError:invalid.append(repr(value))
        else:raise AssertionError('Invalid scope admitted')
    # Compare current full-band code with immutable pre-change code, not with itself.
    legacy_root=Path('E:/VehicleSoundLab/baselines/event_designer_v1/delivery1/examples')
    legacy_sources=next(legacy_root.glob('*/analysis_*/exact_sources'))
    legacy=a.output/'legacy_event_authoring';shutil.copytree(legacy_sources,legacy)
    spec=importlib.util.spec_from_file_location('legacy_event_authoring',legacy/'__init__.py',submodule_search_locations=[str(legacy)])
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    old_measure=importlib.import_module('legacy_event_authoring.measure')
    old_fit=importlib.import_module('legacy_event_authoring.fit')
    legacy_cases=[]
    from event_authoring.audio import read
    for name in ('A_crank','A_catch'):
        job=json.loads((repo/'examples/event_authoring'/f'{name}.job.json').read_text(encoding='utf-8'))
        event,_,_=read(job['source'],*job['seconds']);bg,_,_=read(job['source'],*job['background_seconds'])
        old,oa=old_measure.observe(event,bg);new,na=observe(event,bg)
        check(old==new,'Full-band observation unchanged '+name)
        op,of=old_fit.fit(old,oa,len(event)/48000,job['gated']);np_,nf=fit(new,na,len(event)/48000,job['gated'])
        check(op==np_ and of==nf,'Full-band parameters/fit policy unchanged '+name)
        check(np.array_equal(synth(op,seconds=len(event)/48000),synth(np_,seconds=len(event)/48000)),'Full-band PCM unchanged '+name)
        legacy_cases.append(dict(name=name,observation_parameters_policy_pcm_exact=True))
    workspace=EventWorkspace(repo,a.output/'workspace/events')
    project=workspace.create(dict(upload(source),kind='afterfire',viewpoint='engine'))
    request=dict(id=project['id'],seconds=[.4,1.],background_seconds=[0,.3],gated=False)
    refused=workspace.analyze(request)
    check(refused['analysis']['status']=='analysis_only' and refused['document'] is None,'V1 total-power refusal unchanged')
    project=workspace.analyze(dict(request,analysis_scope=scope,name='Known HF fixture; not a car'))
    check(project['reference_matches_model'] is True,'Scope participates in source binding')
    project=workspace.render(edit(project));root=workspace.root/project['id'];saved=project['history'][0]['id']
    actual,_=sf.read(root/project['last_version']/'synthesis.wav',dtype='float32')
    expected=synth(project['document']['parameters'],seconds=project['controls']['seconds']).astype(np.float32)
    expected=np.pad(expected,(0,len(actual)-len(expected)))
    c_error=float(np.max(abs(actual.astype(float)-expected)))
    check(c_error<2e-7,'Real C preview versus independent synthesis')
    package=json.loads((root/project['last_version']/'parameters.json').read_text(encoding='utf-8'))
    imported=workspace.create(dict(package=package));check(imported['analysis_scope']==scope,'Source-free import retains scope')
    imported=workspace.render(edit(imported))
    imported_pcm,_=sf.read(workspace.root/imported['id']/imported['last_version']/'synthesis.wav',dtype='float32')
    check(np.array_equal(actual,imported_pcm),'Source-free scope import reproduces exact C PCM')
    prior=deepcopy(project['document']['parameters'])
    # An admitted event whose finite-kernel fit fails must also retain the
    # existing editable model; exercising just contrast refusal misses this.
    from unittest.mock import patch
    with patch('event_authoring.fit.fit',return_value=(prior,dict(scope_band_fit_qualified=False,reason='injected infeasible fixed basis'))):
        rejected=workspace.analyze(dict(edit(project),seconds=[.4,1.],background_seconds=[0,.3],gated=False))
    check(rejected['analysis'].get('refusal_kind')=='band_fit' and rejected['document']['parameters']==prior,
        'Unqualified fit preserves existing editable parameters')
    value=edit(project);value['analysis_scope']=dict(mode='full')
    project=workspace.analyze(dict(value,seconds=[.4,1.],background_seconds=[0,.3],gated=False))
    check(project['analysis']['status']=='analysis_only' and project['document']['parameters']==prior and
          project['reference_matches_model'] is False,'Refused scope change preserves model and flags mismatch')
    project=workspace.restore(dict(id=project['id'],revision=saved))
    check(project['analysis_scope']==scope and project['reference_matches_model'] is True,'History restores frequency scope')
    again=workspace.render(edit(project));again_pcm,_=sf.read(root/again['last_version']/'synthesis.wav',dtype='float32')
    check(np.array_equal(actual,again_pcm),'Restored scope C PCM exact')
    # Reject accidental use of V2 semantics with a V1 job; keep old refusals intact.
    job=dict(schema='vsl.event-authoring-job/1',kind='afterfire',name='Invalid mixed protocol',source=str(source.resolve()),
        seconds=[.4,1.],background_seconds=[0,.3],analysis_scope=scope)
    write(a.output/'invalid.job.json',job)
    try:author(a.output/'invalid.job.json',a.output/'invalid')
    except ValueError:pass
    else:raise AssertionError('V1 job silently admitted V2 scope')
    report.update(full_contrast_db=admission(full),scoped_contrast_db=admission(scoped),
        stationary_contrast_db=admission(no_event),known_decay_seconds=scoped['bands'][0]['decay_seconds'],
        scoped_target_relative_error=relative,out_of_band_LF_target_sensitivity=lf_sensitivity,
        dual_band_actual_response_fit=dual_policy['scope_band_fit'],infeasible_basis_refused=True,
        C_max_error=c_error,legacy_cases=legacy_cases,invalid_scopes_rejected=invalid,
        source_binding_scope_checked=True,refusal_preserves_model=True,unqualified_fit_preserves_model=True,source_free_import_pcm_exact=True,
        history_scope_and_pcm_exact=True,renderer_sha256=Renderer(repo).identity)
    if a.ui:
        server=create_server(repo,a.output/'web_workspace',0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_address[1]);ui=a.output/'ui';ui.mkdir()
        node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
        script=repo/'tools/verify_event_band_scope_ui_v1.cjs';shutil.copy2(script,ui/script.name)
        try:
            run=subprocess.run([str(node),str(script),str(node.parents[1]/'node_modules'),str(ui),str(source.resolve()),base],
                cwd=repo,capture_output=True,timeout=180,creationflags=0x08000000)
            (ui/'stdout.log').write_bytes(run.stdout);(ui/'stderr.log').write_bytes(run.stderr)
            check(run.returncode==0,'Browser scoped workflow: '+run.stderr.decode(errors='replace'))
            report['ui']=json.loads((ui/'report.json').read_text(encoding='utf-8'))
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
        check(not thread.is_alive(),'Owned test server closes');report['test_server_closed']=True
    report['result']='passed';write(a.output/'verification.json',report);print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1]);out.mkdir(parents=True,exist_ok=True)
            (out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
