"""Known low-frequency impacts, exact legacy scans and real workbench/C checks."""
import argparse
import base64
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import threading
import zipfile
import numpy as np
import soundfile as sf
from event_authoring.scan import scan_file
from event_designer.workspace import EventWorkspace
from sound_designer.server import create_server
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    data = Path('E:/VehicleSoundLab')
    report = dict(result='running', goal_complete=False, timbre_accepted=False)
    exact = out/'exact_sources'
    files = [Path(__file__), repo/'tools/verify_low_mid_event_scan_web_v1.cjs',
        repo/'research/low_mid_event_scan_v1_plan.json', repo/'tools/scan_approved_event_region.py',
        *sorted((repo/'tools/event_authoring').glob('*.py')),
        *sorted((repo/'tools/event_designer').glob('*.py')),
        *[repo/'tools/sound_designer/web'/name for name in ('events.html','events.js','event_candidates.js')]]
    for path in files:
        target = exact/path.relative_to(repo)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    try:
        rate = 48000
        t = np.arange(3*rate)/rate
        rng = np.random.default_rng(5823)
        floor = rng.normal(0, .0002, len(t))
        impact = .2*np.exp(-.5*((t-1.4)/.015)**2)*(np.sin(2*np.pi*200*t)+.5*np.sin(2*np.pi*700*t))
        stereo = np.column_stack([floor+impact, -(floor+impact)])
        fixture = out/'low-mid-impact.wav'
        sf.write(fixture, stereo, rate, subtype='FLOAT')
        high = scan_file(fixture)
        low = scan_file(fixture, mode='low_mid')
        assert not any(abs(v['source_seconds']-1.4)<.1 for v in high['candidates'])
        nearby = [v for v in low['candidates'] if abs(v['source_seconds']-1.4)<.1]
        assert nearby and all(v['both_full_band_above_3db'] for v in nearby)
        assert low['detector']['frequency_bands_hz']==[[80,300],[300,1200],[1200,3000]]
        save(out/'known-high.json', high);save(out/'known-low-mid.json', low)
        inphase = out/'inphase.wav';mono = out/'mono.wav'
        sf.write(inphase, np.abs(np.array([1.,1.]))*stereo[:,0,None], rate, subtype='FLOAT')
        sf.write(mono, stereo[:,0], rate, subtype='FLOAT')
        assert scan_file(inphase, mode='low_mid')==low
        mono_scan = scan_file(mono, mode='low_mid')
        assert mono_scan['candidates']==low['candidates']
        for name, wave in [('silence',np.zeros_like(t)),
                           ('steady',.03*np.sin(2*np.pi*200*t)+.02*np.sin(2*np.pi*700*t))]:
            file=out/(name+'.wav');sf.write(file,wave,rate,subtype='FLOAT')
            assert not scan_file(file,mode='low_mid')['candidates']
        for invalid in ('unknown',None,1,True,[],{}):
            try:scan_file(fixture, mode=invalid)
            except ValueError:pass
            else:raise AssertionError('Invalid detector admitted')
        report['known']=dict(high_misses_low_impact=True,low_mid_finds_impact=True,
            inphase_antiphase_exact=True,mono_stereo_candidates_exact=True,steady_silence_empty=True,
            impact_candidates=nearby)
        print('Known controls passed',flush=True)
        legacy=[]
        for name,path in [('A',data/'references/analysis/A_exterior_event_v1/scan1/report.json'),
                          ('F3',data/'references/analysis/F3_event_context_v1/scan1/report.json')]:
            old=load(path);actual=scan_file(old['source'],old['requested_ranges'])
            expected=[{k:v for k,v in row.items() if k!='source_id'} for row in old['candidates']]
            assert actual['candidates']==expected and actual['blocks']==old['blocks']
            assert actual['detector']==old['detector']
            legacy.append(dict(source=name,candidates=len(expected),default_exact=True))
        report['legacy']=legacy
        print('Legacy A/F3 candidates exact',flush=True)
        workspace=EventWorkspace(repo,out/'projects')
        def imported(file,kind='afterfire'):
            return workspace.create(dict(filename=file.name,audio=base64.b64encode(file.read_bytes()).decode(),kind=kind))
        p=imported(fixture);p=workspace.scan_candidates(dict(id=p['id'],scan_detector='low_mid'))
        assert p['scan_detector']=='low_mid' and p['document'] is None
        before_file=workspace.root/p['id']/'project.json';before=before_file.read_bytes()
        for invalid in ('bad',None,True,[],{}):
            try:workspace.scan_candidates(dict(id=p['id'],scan_detector=invalid))
            except ValueError:pass
            else:raise AssertionError('Invalid workbench detector admitted')
            assert before_file.read_bytes()==before
        index=next(i for i,v in enumerate(p['candidate_scan']['candidates']) if abs(v['source_seconds']-1.4)<.1)
        p=workspace.use_candidate(dict(id=p['id'],scan_run=p['scan_run'],candidate_index=index))
        assert p['scan_detector']=='low_mid' and not p['document'] and p['context_matches_selection']
        revision=p['history'][0]['id']
        p=workspace.scan_candidates(dict(id=p['id'],scan_detector='high'))
        assert p['scan_detector']=='high'
        p=workspace.restore(dict(id=p['id'],revision=revision))
        assert p['scan_detector']=='low_mid' and p['selected_candidate']['index']==index
        # Actual old C sound remains identical after a new-family scan/selection.
        original=data/'references/analysis/event_sources_v1/timelines1/A_startup/original.wav'
        if not original.exists():
            original=out/'startup-original.wav'
            with sf.SoundFile(data/'references/clean/A_decoded_float.wav') as stream:
                stream.seek(35*rate);x=stream.read(round(5.5*rate),always_2d=True)
            sf.write(original,x,rate,subtype='FLOAT')
        p=imported(original,'catch')
        p=workspace.analyze(dict(id=p['id'],seconds=[2.22,3.02],background_seconds=[0,1.2]))
        p=workspace.render(dict(id=p['id']));folder=workspace.root/p['id']
        old_document=deepcopy(p['document']);old_controls=deepcopy(p['controls'])
        old_pcm,_=sf.read(folder/p['last_version']/'synthesis.wav',dtype='float32')
        p=workspace.scan_candidates(dict(id=p['id'],scan_detector='low_mid'))
        assert p['candidate_scan']['candidates']
        p=workspace.use_candidate(dict(id=p['id'],scan_run=p['scan_run'],candidate_index=0))
        assert p['document']==old_document and p['controls']==old_controls
        p=workspace.render(dict(id=p['id']));version=folder/p['last_version']
        new_pcm,_=sf.read(version/'synthesis.wav',dtype='float32')
        assert np.array_equal(old_pcm,new_pcm)
        package=load(version/'parameters.json')
        assert package['candidate_scan']['report']['detector']['family']=='low_mid'
        assert package['candidate_scan']['matches_current_selection']
        with zipfile.ZipFile(version/'event-design.zip') as archive:
            assert json.loads(archive.read('candidate-scan.json'))==package['candidate_scan']
        assert all(sha(version/name)==value for name,value in load(version/'manifest.json')['files'].items())
        report['workbench']=dict(invalid_preserves_project=True,history_restores_family=True,
            original_C_PCM_exact=True,JSON_ZIP_detector_identity=True,no_automatic_fit_or_label=True)
        print('Workbench/history/export and actual C passed',flush=True)
        server=create_server(repo,out/'browser-root',0)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        node=Path('C:/Users/mlslabs-06/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
        web=out/'web';web.mkdir()
        try:
            run=subprocess.run([str(node),str(repo/'tools/verify_low_mid_event_scan_web_v1.cjs'),
                str(node.parents[1]/'node_modules'),str(web),str(fixture),
                'http://127.0.0.1:'+str(server.server_address[1])],cwd=repo,capture_output=True,
                timeout=180,creationflags=0x08000000)
            (web/'stdout.log').write_bytes(run.stdout);(web/'stderr.log').write_bytes(run.stderr)
            assert run.returncode==0,run.stderr.decode(errors='replace')
            report['browser']=load(web/'report.json')
        finally:server.shutdown();server.server_close();thread.join(timeout=5)
        assert not thread.is_alive()
        baseline=load(data/'references/analysis/low_mid_event_scan_v1/before/runtime.json')
        assert len(baseline)==459 and all(sha(repo/name)==value for name,value in baseline.items())
        report.update(result='passed',runtime_voice_files_unchanged=len(baseline),own_server_closed=True)
    except Exception as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(out/'report.json',report)
    print(dict(result='passed',output=str(out)),flush=True)


if __name__=='__main__':main()
