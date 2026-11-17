"""Exercise short selection through editable exports and the actual C event pool."""
import argparse
import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
import soundfile as sf

from author_event import author
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer,controls
from event_authoring.short_time import layout
from event_designer.media import ranges
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    for path in [Path(__file__),repo/'tools/author_event.py',
                 *sorted((repo/'tools/event_authoring').glob('*.py')),
                 *sorted((repo/'tools/event_designer').glob('*.py'))]:
        target=out/'exact_sources'/path.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    def refused(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('Expected explicit rejection')
    try:
        workspace=EventWorkspace(repo,out/'projects')
        fixture=data/'references/analysis/short_event_scan_v1/probe2/burst-1049.wav'
        assert fixture.is_file()
        p=workspace.create(dict(filename=fixture.name,audio=base64.b64encode(fixture.read_bytes()).decode(),kind='afterfire'))
        key=p['id'];folder=workspace.root/key
        p=workspace.scan_candidates(dict(id=key,scan_detector='short_high'))
        index=next(i for i,row in enumerate(p['candidate_scan']['candidates'])
                   if row['both_full_band_above_3db'] and abs(row['source_seconds']-1.4)<.02)
        p=workspace.use_candidate(dict(id=key,scan_run=p['scan_run'],candidate_index=index))
        assert p['context_matches_selection'] and not p['document']
        assert round(p['selection'][1]*48000)-round(p['selection'][0]*48000)==768
        args=dict(id=key,seconds=p['selection'],background_seconds=p['background_selection'])
        before=(folder/'project.json').read_bytes()
        refused(lambda:workspace.analyze(dict(args,gated=True)))
        refused(lambda:workspace.analyze(dict(args,envelope_fit='band-attack-v1',response_fit='source-response-v1')))
        assert (folder/'project.json').read_bytes()==before
        p=workspace.analyze(args)
        assert p['document']['source_job']['schema']=='vsl.event-authoring-job/10'
        assert p['observation']['time_analysis']==dict(mode='short-event-v1',window_frames=192,hop_frames=48,
            frequency_bin_hz=250.,event_frames=768,
            limitation='Short-window low-frequency and decay estimates are unresolved or fallback; no physical source identification.')
        assert not p['document']['physical_identity_confirmed']
        p=workspace.render(dict(id=key));version=folder/p['last_version']
        native=Renderer(repo);errors=[]
        for seed,pitch,decay in [(1049,1.,1.),(17467,.8,.5),(28123,1.2,2.),(54123,1.1,4.)]:
            values=controls(dict(seed=seed,pitch=pitch,decay=decay,seconds=.2))
            actual,details=native.render(p['document']['parameters'],p['kind'],values)
            expected=synth(p['document']['parameters'],seed=seed,pitch=pitch,decay=decay)
            expected=np.pad(expected,(0,len(actual)-len(expected)))
            error=float(np.max(abs(actual-expected)));assert error<2e-6,error
            assert np.isfinite(actual).all() and not actual[len(synth(p['document']['parameters'],seed=seed,pitch=pitch,decay=decay)):].any()
            errors.append(dict(seed=seed,pitch=pitch,decay=decay,max_error=error))
        package=load(version/'parameters.json')
        q=workspace.create(dict(package=package));q=workspace.render(dict(id=q['id']))
        original,_=sf.read(version/'synthesis.wav',dtype='float32')
        imported,_=sf.read(workspace.root/q['id']/q['last_version']/'synthesis.wav',dtype='float32')
        assert np.array_equal(original,imported) and not q['audio']
        with zipfile.ZipFile(version/'event-design.zip') as archive:
            assert json.loads(archive.read('parameters.json'))==package
            assert {'profile.h','parameters.csv','candidate-scan.json','source-context.json'}<=set(archive.namelist())
        assert all(sha(version/name)==digest for name,digest in load(version/'manifest.json')['files'].items())
        report['short']=dict(project=key,selected_candidate=index,event_frames=768,
            invalid_gated_envelope_preserves_project=True,source_free_C_exact=True,
            JSON_C_CSV_ZIP_export=True,C_python=errors)
        # Endpoints, rather than rounded duration, define the actual sample crop.
        ranges(dict(seconds=[1.00001,1.008],background_seconds=[0,.1]),3)
        refused(lambda:ranges(dict(seconds=[1.000012,1.008],background_seconds=[0,.1]),3))
        assert layout(384)==(192,144) and layout(2879)==(192,144) and layout(2880)==(960,720)
        refused(lambda:layout(383))
        job=dict(schema='vsl.event-authoring-job/1',kind='afterfire',name='Boundary fixture',source=str(fixture),
                 seconds=[1.396,1.412],background_seconds=[1.25,1.35],gated=False)
        jobfile=out/'boundary.job.json';save(jobfile,job)
        refused(lambda:author(jobfile,out/'old-short-refused'))
        for first,last in [(1.396,1.404),(1.396,1.4039791666666667)]:
            value=dict(job,schema='vsl.event-authoring-job/10',seconds=[first,last]);save(jobfile,value)
            if round(last*48000)-round(first*48000)==384:
                result=author(jobfile,out/'eight-ms');assert result.get('status')!='analysis_only'
            else:refused(lambda:author(jobfile,out/'less-eight-refused'))
        report['boundaries']=dict(eight_ms_valid=True,less_eight_refused=True,old_job_short_refused=True,
                                  sixty_ms_legacy_layout=True,sample_endpoint_validation=True)
        # Non-grid seconds can round a duration differently from its endpoints.
        refused(lambda:ranges(dict(seconds=[1000.51/48000,1384.49/48000],background_seconds=[.1,.2]),1.))
        actual=ranges(dict(seconds=[1000.49/48000,1383.51/48000],background_seconds=[.1,.2]),1.)
        assert round(actual[0][1]*48000)-round(actual[0][0]*48000)==384
        refused(lambda:ranges(dict(seconds=[.4,.416],background_seconds=[.1,.159]),1.))
        # Independent frozen legacy measurement keeps every scalar/array exact.
        frozen=data/'baselines/event_full_envelope_v1/delivery1/repo/tools/event_authoring/measure.py'
        spec=importlib.util.spec_from_file_location('event_authoring.frozen_measure',frozen)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        comparisons=[]
        for name,start,stop,bstart,bstop in [('A',37.22,38.02,35.,36.2),('B',19.,19.8,18.,18.5)]:
            master=data/('references/clean/'+name+'_decoded_float.wav')
            from event_authoring.audio import read
            x,_,_=read(master,start,stop);bg,_,_=read(master,bstart,bstop)
            legacy,arrays=old.observe(x,bg);current,current_arrays=observe(x,bg)
            assert current==legacy
            assert all(np.array_equal(a,b) for a,b in zip(arrays,current_arrays))
            from event_authoring.fit import fit
            profile,_=fit(current,current_arrays,len(x)/48000)
            frozen_profile,_=fit(legacy,arrays,len(x)/48000)
            a,_=native.render(profile,'catch',controls({}));b,_=native.render(frozen_profile,'catch',controls({}))
            assert np.array_equal(a,b)
            comparisons.append(dict(source=name,measurement_arrays_exact=True,profile_C_exact=True))
        report['legacy']=dict(frozen_measure_path=str(frozen),frozen_measure_sha256=sha(frozen),cases=comparisons)
        baseline=load(data/'references/analysis/low_mid_event_scan_v1/before/runtime.json')
        assert len(baseline)==459 and all(sha(repo/name)==digest for name,digest in baseline.items())
        report.update(result='passed',runtime_voice_files_unchanged=459,no_C_or_bank_change=True)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(json.dumps(dict(result=report['result'],output=str(out)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
