"""Exercise the public authoring API, existing-C parity and preset recovery."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8791')
    parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from sound_designer.models import DEFAULTS
    from research_archive_v1 import save,sha
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    report=dict(result='running',checks=[])

    def get(path):
        with urllib.request.urlopen(a.url+path,timeout=20) as response:return response.read()
    def task(path,data):
        request=urllib.request.Request(a.url+path,json.dumps(data).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=20) as response:key=json.load(response)['job']
        limit=time.monotonic()+120
        while time.monotonic()<limit:
            value=json.loads(get('/api/job/'+key))
            if value['status']=='done':return value['result']
            if value['status']=='error':raise ValueError(value['error'])
            time.sleep(.1)
        raise TimeoutError(key)
    try:
        p=task('/api/new',dict(preset='v10'))
        neutral=dict(DEFAULTS,gain_db=0.,seconds=.25)
        result=task('/api/render',dict(id=p['id'],params=neutral))
        new,rate=sf.read(io.BytesIO(get(result['audio'])),always_2d=True)
        exe=repo/'build-sound-dna-export-v1/bin/Release/sound_dna_export.exe'
        reference=a.out/'direct_C.wav'
        subprocess.run([str(exe),str(repo/'voices/dna_bank_v1/V10 Exterior.model'),str(reference),'.25','1','1','48271','512'],check=True,capture_output=True)
        expected,rate2=sf.read(reference,always_2d=True)
        assert rate==rate2==48000 and np.array_equal(new,expected)
        report['checks'].append('neutral_parameter_edit_matches_original_C_all_samples')
        package=json.loads(get(result['parameters']))
        restored=task('/api/new',dict(package=package))
        again=task('/api/render',dict(id=restored['id'],params=restored['params'],rows=restored['rows'],rho=restored['rho']))
        assert np.array_equal(sf.read(io.BytesIO(get(again['audio'])))[0],new)
        assert not restored['has_audio']
        report['checks'].append('parameter_JSON_restore_and_replay_exact_without_audio')
        with zipfile.ZipFile(io.BytesIO(get(result['bundle']))) as archive:
            assert set(archive.namelist())=={'voice.model','parameters.json','harmonics.csv','analysis.json','preview.wav'}
        report['checks'].append('complete_export_bundle')
        n=np.arange(96000);f=47.
        audio=np.column_stack((.12*np.cos(2*np.pi*f*n/48000)+.04*np.cos(2*np.pi*3*f*n/48000+.7),
                               .09*np.cos(2*np.pi*f*n/48000+.3)+.03*np.cos(2*np.pi*3*f*n/48000+1.)))
        source=a.out/'合成已知片段.wav';sf.write(source,audio,48000,subtype='FLOAT')
        p=task('/api/new',dict(filename=source.name,audio=base64.b64encode(source.read_bytes()).decode(),state='steady',viewpoint='exterior'))
        assert any(abs(c['hz']-f)<1 for c in p['analysis']['root_candidates'])
        assert p['analysis']['channels']==2 and p['analysis']['stereo_correlation'] is not None
        p=task('/api/analyze',dict(id=p['id'],start=.1,end=1.9,root_hz=f))
        assert p['analysis']['stable_candidate']
        p=task('/api/compile',dict(id=p['id'],root_hz=f,harmonics=128,components=8,state='steady',viewpoint='exterior'))
        assert p['model']['harmonics']==128 and p['model']['root_hz']==f
        result=task('/api/render',dict(id=p['id'],params=dict(DEFAULTS,seconds=.5)))
        generated,sr=sf.read(io.BytesIO(get(result['audio'])),always_2d=True)
        assert generated.shape==(24000,2) and sr==48000 and np.isfinite(generated).all()
        report['checks'].append('unicode_audio_to_measurements_to_parameter_table_to_C_preview')
        changed=task('/api/render',dict(id=p['id'],params=dict(DEFAULTS,seconds=.5,high_db=3,width=.4,shared=.3)))
        modified=sf.read(io.BytesIO(get(changed['audio'])))[0]
        assert not np.array_equal(modified,generated)
        report['checks'].append('exposed_controls_change_actual_C_output')
        rows=p['model']['rows'];rows[0]['phase_l']+=90
        phase=task('/api/render',dict(id=p['id'],params=dict(DEFAULTS,seconds=.5),rows=rows))
        assert not np.array_equal(sf.read(io.BytesIO(get(phase['audio'])))[0],generated)
        phase_samples=sf.read(io.BytesIO(get(phase['audio'])))[0]
        revisions=json.loads(get('/api/history/'+p['id']))
        phase_revision=next(v['id'] for v in revisions if v['preview_version']==phase['project']['last_version'])
        snapshot=get('/files/'+p['id']+'/history/'+phase_revision+'.json')
        report['checks'].append('individual_phase_edit_changes_output')
        draft=task('/api/save',dict(id=p['id'],name='Saved draft',params=dict(DEFAULTS,high_db=2),rows=rows))
        saved=json.loads(get('/api/project/'+p['id']))
        assert saved['params']['high_db']==2 and saved['preview_stale'] and saved['rows']==rows
        assert any(item['id']==p['id'] for item in json.loads(get('/api/projects')))
        report['checks'].append('saved_edits_and_recent_projects_reopen_without_render')
        changed_selection=task('/api/analyze',dict(id=p['id'],start=.3,end=1.5,root_hz=f,
            draft=dict(params=dict(DEFAULTS,high_db=5),rows=rows,name='Before extraction')))
        assert changed_selection['params']['high_db']==5 and changed_selection['rows']==rows
        assert changed_selection['reference_matches_model'] is False
        assert changed_selection['model_reference']['selection']==[.1,1.9]
        mismatch=task('/api/render',dict(id=p['id'],params=dict(DEFAULTS,seconds=.25)))
        mismatch_package=json.loads(get(mismatch['parameters']))
        assert mismatch_package['reference_matches_model'] is False
        assert mismatch_package['selection']==[.3,1.5] and mismatch_package['model_reference']['selection']==[.1,1.9]
        recompiled=task('/api/compile',dict(id=p['id'],root_hz=f,harmonics=96,components=8))
        assert recompiled['reference_matches_model'] is True and recompiled['model']['harmonics']==96
        recovered=task('/api/restore',dict(id=p['id'],revision=phase_revision))
        assert recovered['model']['harmonics']==128 and recovered['selection']==[.1,1.9]
        assert recovered['reference_matches_model'] is True and recovered['rows']==rows
        replay=task('/api/render',dict(id=p['id'],params=recovered['params'],rows=recovered['rows'],rho=recovered['rho']))
        assert np.array_equal(sf.read(io.BytesIO(get(replay['audio'])))[0],phase_samples)
        assert get('/files/'+p['id']+'/history/'+phase_revision+'.json')==snapshot
        report['checks'].append('reextract_and_restore_model_edits_selection_C_audio_and_immutable_history')
        report['checks'].append('reference_and_training_analysis_remain_separate_in_export')
        empty_basis=package.copy();empty_basis['base_profile']=dict(package['base_profile'])
        empty_basis['base_profile'].update(basis=[[] for _ in package['base_profile']['mean']],rho=[])
        zero=task('/api/new',dict(package=empty_basis))
        assert zero['model']['components']==0
        report['checks'].append('zero_component_JSON_roundtrip')
        # A changing-pitch clip is analyzable, but not silently presented as a fixed voice.
        phase=2*np.pi*(40*n/48000+20*(n/48000)**2)
        varying=.1*np.cos(phase);stream=io.BytesIO();sf.write(stream,varying,48000,format='WAV',subtype='FLOAT')
        moving=task('/api/new',dict(filename='rising.wav',audio=base64.b64encode(stream.getvalue()).decode()))
        assert not moving['analysis']['stable_candidate']
        high_stream=io.BytesIO();sf.write(high_stream,.1*np.cos(2*np.pi*400*n/48000),48000,format='WAV',subtype='FLOAT')
        high=task('/api/new',dict(filename='high.wav',audio=base64.b64encode(high_stream.getvalue()).decode()))
        high=task('/api/analyze',dict(id=high['id'],start=0,end=2,root_hz=400))
        failures=[]
        for label,path,data in (
            ('nan_control','/api/render',dict(id=p['id'],params=dict(DEFAULTS,width=float('nan')))),
            ('invalid_range','/api/analyze',dict(id=p['id'],start=-1,end=1,root_hz=f)),
            ('unsafe_harmonics','/api/compile',dict(id=high['id'],root_hz=400,harmonics=320,components=8,allow_unstable=True)),
            ('bad_profile','/api/new',dict(package=dict(package,root_hz=2000))),
            ('variable_pitch_without_optin','/api/compile',dict(id=moving['id'],root_hz=moving['analysis']['root_hz'],harmonics=128,components=8)),
            ('restored_JSON_has_no_original_audio','/api/analyze',dict(id=restored['id'],start=0,end=1,root_hz=47)),
            ('root_not_analyzed','/api/compile',dict(id=p['id'],root_hz=80,harmonics=128,components=8)),
            ('bad_history_identity','/api/restore',dict(id=p['id'],revision='../project')),
        ):
            try:task(path,data)
            except ValueError:failures.append(label)
            else:raise AssertionError('Invalid authoring input accepted: '+label)
        assert len(failures)==8
        report.update(result='passed',invalid_inputs_rejected=failures,
                      browser_fixture=str(source),project_id=p['id'],renderer_sha256=sha(exe),
                      no_core_C_changes=True,goal_complete=False)
    except BaseException as error:
        report.update(result='failed',error=repr(error));raise
    finally:save(a.out/'report.json',report)
    print(report['result'],report['checks'],flush=True)


if __name__=='__main__':main()
