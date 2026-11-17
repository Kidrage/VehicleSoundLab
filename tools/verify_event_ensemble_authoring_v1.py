"""Exercise optional multi-realization fitting through projects, actual C and exports."""
import argparse
import base64
from copy import deepcopy
import csv
import importlib.util
from pathlib import Path
import shutil
import zipfile

import numpy as np
import soundfile as sf

from author_event import author
from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer,controls
from event_authoring.response_ensemble import TRAIN_SEEDS,HELD_OUT_SEEDS,assess,target_powers
from event_designer.workspace import EventWorkspace
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];data=Path('E:/VehicleSoundLab')
    report=dict(result='running',goal_complete=False,timbre_accepted=False)
    for path in [Path(__file__),repo/'tools/author_event.py',repo/'research/event_ensemble_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py')),
                 *sorted((repo/'tools/event_designer').glob('*.py'))]:
        target=out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    def refused(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('Expected explicit rejection')
    try:
        probe=data/'references/analysis/event_ensemble_v1/probe1'
        assert load(probe/'report.json')['result']=='passed'
        jobs={name:load(probe/name/'source-job.json') for name in ('B_rank3','B_rank6','A_crank','A_catch')}
        workspace=EventWorkspace(repo,out/'projects');native=Renderer(repo)
        job=jobs['B_rank6'];source=Path(job['source'])
        p=workspace.create(dict(filename=source.name,audio=base64.b64encode(source.read_bytes()).decode(),kind=job['kind']))
        key=p['id'];folder=workspace.root/key
        args=dict(id=key,seconds=job['seconds'],background_seconds=job['background_seconds'],
                  response_fit='source-response-ensemble-v1',envelope_fit='legacy',gated=False)
        before=(folder/'project.json').read_bytes()
        for extra in [dict(analysis_scope=dict(mode='band',low_hz=1200,high_hz=14000)),
                      dict(envelope_fit='band-attack-v1'),dict(gated=True)]:
            refused(lambda extra=extra:workspace.analyze(dict(args,**extra)))
            assert (folder/'project.json').read_bytes()==before
        p=workspace.analyze(args)
        assert p['document']['source_job']['schema']=='vsl.event-authoring-job/11'
        assert p['analysis']['response_summary']==dict(method='source-response-ensemble-v1',
            training_qualified=True,held_out_qualified=True,qualified=True)
        assert p['document']['parameters']==load(probe/'B_rank6/profile.json')
        assert p['reference_matches_model'] and not p['document']['physical_identity_confirmed']
        x,_,_=read(folder/'master.wav',*job['seconds']);bg,_,_=read(folder/'master.wav',*job['background_seconds'])
        _,arrays=observe(x,bg);targets=target_powers(arrays)
        checks=[]
        for seed in (*TRAIN_SEEDS,*HELD_OUT_SEEDS):
            values=controls(dict(seed=seed,seconds=.2))
            actual,details=native.render(p['document']['parameters'],p['kind'],values)
            expected=synth(p['document']['parameters'],seed=seed)
            error=float(np.max(abs(actual[:len(expected)]-expected)))
            assert error<2e-6 and not actual[len(expected):].any()
            # The independent C waveform must satisfy the same six band gates.
            from event_authoring.response_ensemble import band_powers
            powers=band_powers(actual[:len(expected)]);total=float(targets.sum())
            for target,power in zip(targets,powers):
                assert abs(10*np.log10(power/target))<=3 if target>=total*1e-4 else power<=max(2*target,2e-4*total)
            checks.append(dict(seed=seed,C_python_error=error,all_six_bands=True))
        p=workspace.render(dict(id=key));version=folder/p['last_version'];package=load(version/'parameters.json')
        q=workspace.create(dict(package=package));q=workspace.render(dict(id=q['id']))
        original,_=sf.read(version/'synthesis.wav',dtype='float32')
        imported,_=sf.read(workspace.root/q['id']/q['last_version']/'synthesis.wav',dtype='float32')
        assert np.array_equal(original,imported) and not q['audio']
        with zipfile.ZipFile(version/'event-design.zip') as archive:
            import json
            assert json.loads(archive.read('parameters.json'))==package
            assert {'profile.h','parameters.csv','manifest.json','synthesis.wav'}<=set(archive.namelist())
        assert all(sha(version/name)==digest for name,digest in load(version/'manifest.json')['files'].items())
        rows=list(csv.DictReader((version/'parameters.csv').open(encoding='utf-8-sig')))
        params=p['document']['parameters']
        for kind in ('modes','bands'):
            for index,row in enumerate(params[kind]):
                for field,value in row.items():
                    cell=next(r for r in rows if r['group']==kind and r['index']==str(index) and r['parameter']==field)
                    assert float(cell['value'])==value
        revision=p['history'][0]['id']
        altered=deepcopy(params);altered['level']*=.7
        workspace.save(dict(id=key,parameters=altered))
        restored=workspace.restore(dict(id=key,revision=revision))
        assert restored['document']==p['document'] and restored['last_version']==p['last_version']
        report['qualified_project']=dict(project=key,profile_exact_to_probe=True,job11=True,
            actual_C_eight_seeds=checks,JSON_C_CSV_ZIP_checked=True,source_free_C_PCM_exact=True,
            history_restores_profile_preview=True,invalid_requests_preserve_project=True)
        print('B rank6: job11, eight actual C triggers, history and source-free exports passed',flush=True)
        # A failed new fit must preserve a usable earlier document and preview.
        job=jobs['B_rank3'];source=Path(job['source'])
        r=workspace.create(dict(filename=source.name,audio=base64.b64encode(source.read_bytes()).decode(),kind=job['kind']))
        rejected_args=dict(id=r['id'],seconds=job['seconds'],background_seconds=job['background_seconds'])
        r=workspace.analyze(rejected_args);r=workspace.render(dict(id=r['id']))
        prior=deepcopy(r['document']);prior_version=r['last_version']
        preview=workspace.root/r['id']/prior_version/'synthesis.wav';digest=sha(preview)
        r=workspace.analyze(dict(rejected_args,response_fit='source-response-ensemble-v1'))
        assert r['analysis']['status']=='analysis_only' and not r['analysis']['response_summary']['qualified']
        assert r['document']==prior and r['last_version']==prior_version and sha(preview)==digest
        refused_root=workspace.root/r['id']/r['analysis_run']
        assert (refused_root/'refused-fit.json').is_file() and not (refused_root/'profile.json').exists()
        assert load(refused_root/'report.json')['fit']['source_response_fit']['method']=='source-response-ensemble-v1'
        report['refused_project']=dict(project=r['id'],old_document_preview_preserved=True,
            rejected_parameters_and_full_report_retained=True,analysis_summary_qualified=False)
        print('B rank3: rejected fit preserved earlier parameters and C preview',flush=True)
        long_cases=[]
        for name in ('A_crank','A_catch'):
            job=dict(jobs[name],schema='vsl.event-authoring-job/11',response_fit='source-response-ensemble-v1')
            path=out/(name+'.job.json');save(path,job);result=author(path,out/name)
            assert result['response_summary']['qualified']
            doc=load(out/name/'profile.json');assert doc['parameters']==load(probe/name/'profile.json')
            # Gated crank release and finite catch must both survive actual C.
            values=controls(dict(seconds=1.,hold_seconds=.22,seed=54123))
            actual,_=native.render(doc['parameters'],doc['kind'],values)
            expected=synth(doc['parameters'],seconds=1.,seed=54123,
                release_at=.22 if doc['parameters']['gated'] else None)
            error=float(np.max(abs(actual-np.pad(expected,(0,len(actual)-len(expected))))));assert error<2e-6
            long_cases.append(dict(name=name,gated=doc['parameters']['gated'],qualified=True,C_python_error=error))
            print(name,'job11 and C gate/release passed',flush=True)
        report['long_events']=long_cases
        bad=jobs['B_rank6']
        variants=[dict(schema='vsl.event-authoring-job/10',response_fit='source-response-ensemble-v1'),
            dict(schema='vsl.event-authoring-job/11',response_fit='legacy'),
            dict(schema='vsl.event-authoring-job/11',response_fit='source-response-ensemble-v1',
                analysis_scope=dict(mode='band',low_hz=1200,high_hz=14000)),
            dict(schema='vsl.event-authoring-job/11',response_fit='source-response-ensemble-v1',envelope_fit='band-attack-v1'),
            dict(schema='vsl.event-authoring-job/11',response_fit='source-response-ensemble-v1',gated=True),
            dict(schema='vsl.event-authoring-job/11',response_fit='source-response-ensemble-v1',seconds=[.996,1.003])]
        for i,change in enumerate(variants):
            path=out/f'invalid-{i}.job.json';save(path,dict(bad,**change))
            refused(lambda path=path,i=i:author(path,out/f'invalid-{i}'))
            assert not (out/f'invalid-{i}').exists()
        report['invalid_jobs_refused_before_output']=len(variants)
        # Execute the frozen author, rather than merely comparing source text.
        frozen=data/'baselines/short_event_authoring_v1/delivery1/repo/tools/author_event.py'
        spec=importlib.util.spec_from_file_location('frozen_event_author',frozen)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for name,change in [('short',dict(jobs['B_rank6'],schema='vsl.event-authoring-job/10',response_fit='source-response-v1')),
                            ('long',dict(jobs['A_crank'],schema='vsl.event-authoring-job/1',response_fit='legacy'))]:
            path=out/f'legacy-{name}.job.json';save(path,change)
            a=author(path,out/f'legacy-{name}-current');b=old.author(path,out/f'legacy-{name}-frozen')
            assert {k:v for k,v in a.items() if k!='output'}=={k:v for k,v in b.items() if k!='output'}
            assert load(Path(a['output'])/'profile.json')==load(Path(b['output'])/'profile.json')
            wave_a,_=sf.read(Path(a['output'])/'synthesis.wav',dtype='float32')
            wave_b,_=sf.read(Path(b['output'])/'synthesis.wav',dtype='float32')
            assert np.array_equal(wave_a,wave_b)
        runtime=load(data/'references/analysis/short_event_scan_v1/runtime.json')
        assert len(runtime)==459 and all(sha(repo/name)==digest for name,digest in runtime.items())
        report.update(result='passed',legacy_short_and_long_author_exact=True,runtime_unchanged=459,
            no_bank_change=True,physical_afterfire_confirmed=False,author_DLL_sha256=native.identity)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result=report['result'],output=str(out)),flush=True)


if __name__=='__main__':main()
