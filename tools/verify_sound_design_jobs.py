"""End-to-end CLI contract, repeatability, labels and refusal evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    repo = Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', checks=[], cases=[])
    n = np.arange(96000) / 48000
    audio = np.column_stack((.12*np.cos(2*np.pi*47*n)+.04*np.cos(2*np.pi*141*n+.7),
                             .09*np.cos(2*np.pi*47*n+.3)+.03*np.cos(2*np.pi*141*n+1.)))
    source = a.out / '已裁剪 声浪.wav'
    sf.write(source, audio, 48000, subtype='FLOAT')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    base = dict(schema='vsl.sound-design-job/1', name='工程怠速', audio=source.name,
                state='idle', viewpoint='cabin', selection=dict(start=.1, end=1.9),
                root_hz=47, harmonics=128, components=8,
                parameters=dict(seconds=.5, gain_db=-6, seed=48271))

    def run(label, job, code=0, extra=(), wrapper=False):
        spec = a.out / (label + '.job.json')
        spec.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
        output = a.out / label
        if wrapper:
            command = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(repo/'Design-Sound-Clip.ps1'),
                       '-Job', str(spec), '-Out', str(output), '-Workspace', str(a.workspace)]
        else:
            command = [sys.executable, str(repo/'tools/design_sound_clip.py'), str(spec), '--out', str(output),
                       '--workspace', str(a.workspace), *extra]
        result = subprocess.run(command, capture_output=True, timeout=90)
        (a.out/(label+'.stdout.txt')).write_bytes(result.stdout)
        (a.out/(label+'.stderr.txt')).write_bytes(result.stderr)
        assert result.returncode == code, (label, result.returncode, result.stdout, result.stderr)
        value = json.loads(result.stdout.decode().strip().splitlines()[-1])
        report['cases'].append(dict(label=label, exit_code=result.returncode, status=value['status']))
        return value, output

    try:
        first, output = run('生成一', base)
        assert first['status'] == 'generated' and first['compiled']
        parameters = json.loads((output/'parameters.json').read_text(encoding='utf-8'))
        assert parameters['state'] == 'idle' and parameters['viewpoint'] == 'cabin' and parameters['name'] == base['name']
        assert parameters['reference_matches_model'] is True
        assert first['job_sha256'] == hashlib.sha256((a.out/'生成一.job.json').read_bytes()).hexdigest()
        assert (output/'job.input.json').read_bytes() == (a.out/'生成一.job.json').read_bytes()
        toolchain=json.loads((output/'toolchain.json').read_text(encoding='utf-8'))
        assert toolchain['source_sha256']['tools/sound_designer/jobs.py']==hashlib.sha256((repo/'tools/sound_designer/jobs.py').read_bytes()).hexdigest()
        assert first['toolchain_sha256']==hashlib.sha256((output/'toolchain.json').read_bytes()).hexdigest()
        report['checks'].append('Unicode_relative_audio_job_to_C_preview_with_exact_input_receipt')
        second, repeated = run('生成二', base, wrapper=True)
        assert (output/'voice.model').read_bytes() == (repeated/'voice.model').read_bytes()
        assert np.array_equal(sf.read(output/'preview.wav')[0], sf.read(repeated/'preview.wav')[0])
        report['checks'].append('PowerShell_and_Python_repeat_same_model_and_all_C_audio_samples')
        project = json.loads((a.workspace/'designs'/first['project_id']/'project.json').read_text(encoding='utf-8'))
        assert project['name'] == base['name'] and project['state'] == 'idle' and project['viewpoint'] == 'cabin'
        assert project['build']['name'] == base['name']
        report['checks'].append('explicit_name_state_viewpoint_preserved_across_analysis_compile_and_export')
        inspect, folder = run('只分析', dict(base, root_hz=None), extra=('--inspect',))
        assert inspect['status'] == 'analyzed' and not (folder/'voice.model').exists()
        pending, folder = run('待确认', dict(base, root_hz=None), code=3)
        assert pending['status'] == 'root_confirmation_required' and not (folder/'voice.model').exists()
        report['checks'].append('analysis_only_and_unconfirmed_root_never_silently_compile')
        varying = a.out/'rising.wav';sf.write(varying, .1*np.cos(2*np.pi*(40*n+20*n*n)),48000,subtype='FLOAT')
        pending, folder = run('变音高', dict(base, audio=varying.name), code=4)
        assert pending['status'] == 'stable_crop_required' and not (folder/'voice.model').exists()
        draft, folder = run('变音高草稿',dict(base,audio=varying.name,state='acceleration',allow_unstable=True))
        assert draft['status']=='generated' and draft['fixed_timbre_draft'] and not draft['listening_accepted']
        report['checks'].append('variable_pitch_requires_explicit_draft_optin')
        for label, job in (
            ('未知字段', dict(base, cylinder_count=10)),
            ('错误状态', dict(base, state='race')),
            ('字符串布尔', dict(base, allow_unstable='false')),
            ('假哈希', dict(base, source_sha256='0'*64)),
            ('越界频率', dict(base, root_hz=400, harmonics=320, allow_unstable=True)),
            ('错误选区', dict(base, selection=dict(start=1.8,end=3.0))),
        ):
            bad, folder = run(label,job,code=2)
            assert bad['status'] == 'failed' and not (folder/'voice.model').exists()
        # Existing output is refused before any of its evidence can be replaced.
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
        result = subprocess.run([sys.executable,str(repo/'tools/design_sound_clip.py'),str(a.out/'生成一.job.json'),
            '--out',str(output),'--workspace',str(a.workspace)],capture_output=True,timeout=30)
        assert result.returncode == 2
        assert before == {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        report['checks'].append('invalid_specs_and_overwrite_refused_original_audio_unchanged')
        report.update(result='passed',first_project=first['project_id'],source_sha256=source_hash,
                      model_sha256=hashlib.sha256((output/'voice.model').read_bytes()).hexdigest(),
                      renderer_sha256=first['render_report']['renderer_sha256'],no_C_changes=True,goal_complete=False)
    except BaseException as error:
        report.update(result='failed',error=repr(error));raise
    finally:
        (a.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(report['result'],report['checks'])


if __name__ == '__main__': main()
