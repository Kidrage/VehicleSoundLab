"""Source-only C passage check; deliberately does not bypass the driving controller."""
import argparse
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, urljoin
from urllib.request import urlopen

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--ffmpeg', type=Path, required=True)
parser.add_argument('--regression-proof', type=Path, help='Reuse a verified40-test log for unchanged C/H')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal
import soundfile as sf
from drive_evidence_v1.sources import read, sha
from sound_dna.profile import export

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.state-passage/1', result='running', commands=[], controls=[], passages=[],
              source_only=True, driving_controller_changed=False, human_accepted=False,
              source_sha256={}, input_sha256={})
sources = [Path(__file__), repo/'tools/drive_evidence_v1/sources.py', repo/'tools/sound_dna/profile.py']
for folder in ('experiments/state_passage_v1', 'modules/dna_atlas', 'modules/sound_dna', 'modules/harmonic_body'):
    sources.extend(p for p in (repo/folder).iterdir() if p.is_file())
sources.extend(repo/p for p in ('src/io/file.c', 'src/io/file.h', 'src/io/wav.c', 'src/io/wav.h'))
for path in sources:
    target = args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    report['source_sha256'][path.relative_to(repo).as_posix()] = sha(path)


def command(argv, expected=0):
    log = args.out/('command_%02d.log' % len(report['commands']))
    try:
        result = subprocess.run([str(v) for v in argv], cwd=repo, capture_output=True,
                                timeout=600 if str(argv[0]) == 'ctest' else 60)
    except subprocess.TimeoutExpired as exc:
        log.write_bytes((exc.stdout or b'')+(exc.stderr or b''))
        report['commands'].append(dict(argv=[str(v) for v in argv], timed_out=True,
                                       log=log.name, sha256=sha(log)))
        raise
    log.write_bytes(result.stdout + result.stderr)
    report['commands'].append(dict(argv=[str(v) for v in argv], exit_code=result.returncode,
                                   log=log.name, sha256=sha(log)))
    assert result.returncode == expected, (argv, result.returncode, log)
    return result


def schedule(path, frames, roots):
    assert frames[0] == 0 and np.all(np.diff(frames) > 0)
    path.write_text(''.join(f'{int(n)} {float(hz):.17g}\n' for n, hz in zip(frames, roots)),
                    encoding='ascii', newline='\n')


def invoke(path, prefix, models, detail=1, alignment=8):
    command([probe, path, prefix.with_suffix('.wav'), prefix.with_suffix('.csv'),
             detail, 48271, alignment, *models])
    x, rate = sf.read(prefix.with_suffix('.wav'), always_2d=True)
    assert rate == 48000 and x.shape[1] == 2 and np.isfinite(x).all()
    return x


try:
    # Existing C/H identity is checked before any build. Old binaries/models are untouched.
    prior_index = args.workspace/'baselines/system_status_v1/docs/C文件索引.csv'
    assert sha(prior_index) == '424b3d3680b6d8dd8faf60e3d1b06d8c72ec3df74422997fdf3656423255fb6a'
    report['input_sha256'][str(prior_index)] = sha(prior_index)
    with prior_index.open(encoding='utf-8-sig', newline='') as stream:
        prior = list(csv.DictReader(stream))
    assert len(prior) == 442
    for row in prior:
        assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
    report['prior442_C_H_unchanged'] = True
    build = repo/'build-state-passage-v1'
    command(['cmake', '-S', repo/'experiments/state_passage_v1', '-B', build, '-A', 'x64'])
    command(['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
    probe = build/'Release/state_passage_probe.exe'
    shutil.copy2(probe, args.out/probe.name)
    probe = args.out/probe.name
    report['probe_sha256'] = sha(probe)
    if args.regression_proof:
        proof = json.loads(args.regression_proof.read_text(encoding='utf-8'))
        assert proof['result'] == 'source_host_technical_pass_only'
        for name, digest in proof['source_sha256'].items():
            if Path(name).suffix in ('.c', '.h'):
                assert sha(repo/name) == digest, name
        test = next(row for row in proof['commands'] if row['argv'][0] == 'ctest')
        log = args.regression_proof.parent/test['log']
        assert test['exit_code'] == 0 and sha(log) == test['sha256']
        assert re.search(rb'(?m)^100% tests passed(?:, 0 tests failed)? out of 40\r?$', log.read_bytes())
        report['input_sha256'].update({str(args.regression_proof): sha(args.regression_proof), str(log): sha(log)})
        shutil.copy2(log, args.out/'ctest_reused.log')
        report['regression'] = dict(tests=40, reused=True, proof=str(args.regression_proof),
                                    log_sha256=sha(log), condition='All442prior and every newly built C/H unchanged')
    else:
        command(['ctest', '--test-dir', repo/'handoff-build', '-C', 'Release', '--parallel', '4', '--output-on-failure'])
        assert re.search(rb'(?m)^100% tests passed(?:, 0 tests failed)? out of 40\r?$',
                         (args.out/report['commands'][-1]['log']).read_bytes())
        report['regression'] = dict(tests=40, reused=False)

    controls = args.out/'controls'
    controls.mkdir()
    means = [np.array([.2, .08, .12, -.03]), np.array([.3, -.04, .18, .02])]
    models = []
    for i, (base, mean) in enumerate(zip((20., 80.), means)):
        path = controls/f'model{i}.model'
        export(path, dict(mean=mean[None, :], basis=np.zeros((1, 0, 4)), rho=np.zeros(0),
                          residual_rho=np.zeros(1), root=np.zeros((1, 4, 4))), base)
        models.append(path)
    frames = np.array([0, 4000, 14000, 20000, 28800])
    roots = np.array([20., 20., 80., 25., 25.])
    trajectory = controls/'known.txt'
    schedule(trajectory, frames, roots)
    target = np.interp(np.arange(frames[-1]), frames, roots)
    alpha = 1-np.exp(-1/(.018*48000))
    actual, _ = signal.lfilter([alpha], [1, -(1-alpha)], target, zi=[(1-alpha)*target[0]])
    phase = 2*np.pi*np.r_[0., np.cumsum(actual[:-1])]/48000
    for count in (1, 2):
        x = invoke(trajectory, controls/f'known{count}', models[:count], detail=0, alignment=0)
        blend = np.clip((actual-20)/60, 0, 1) if count == 2 else np.zeros(len(x))
        oracle = np.empty_like(x)
        for c in (0, 1):
            z = [complex(m[c*2], m[c*2+1]) for m in means]
            angle0, angle1 = np.angle(z)
            delta_l = np.angle(np.exp(1j*(np.angle(complex(*means[1][:2]))-np.angle(complex(*means[0][:2])))))
            relative0 = np.angle(complex(*means[0][2:]))-np.angle(complex(*means[0][:2]))
            relative1 = np.angle(complex(*means[1][2:]))-np.angle(complex(*means[1][:2]))
            delta = delta_l if c == 0 else delta_l+np.angle(np.exp(1j*(relative1-relative0)))
            magnitude = abs(z[0])+blend*(abs(z[1])-abs(z[0]))
            oracle[:, c] = magnitude*np.cos(phase+angle0+blend*delta)
        error = float(abs(x-oracle).max())
        assert error < (3e-8 if count == 1 else 2e-7), error
        trace = np.genfromtxt(controls/f'known{count}.csv', delimiter=',', names=True)
        freq_error = float(abs(trace['actual_acoustic_hz']-actual[trace['frame'].astype(int)]).max())
        assert freq_error < 1e-10
        report['controls'].append(dict(anchors=count, independent_sine_error_FS=error,
                                       follower_error_hz=freq_error, frames=len(x)))
    invalid = ['1 30\n20 40\n', '0 30\n0 40\n', '0 nan\n10 30\n',
               '0 30\n8640001 30\n', '0 30 extra\n10 30\n', '0 30\n']
    for i, text in enumerate(invalid):
        path = controls/f'invalid{i}.txt'
        path.write_text(text, encoding='ascii', newline='\n')
        prefix = controls/f'rejected{i}'
        command([probe, path, prefix.with_suffix('.wav'), prefix.with_suffix('.csv'), 1, 48271, 0, models[0]], expected=2)
        assert not prefix.with_suffix('.wav').exists() and not prefix.with_suffix('.csv').exists()
    report['invalid_trajectories_rejected_before_output'] = len(invalid)

    frozen = args.workspace/'baselines/exterior_anchors_v1'
    manifest_path = frozen/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    bound = {row['path']: row['sha256'] for row in manifest['files']}
    old_path = frozen/'evidence/anchors_v2/build.json'
    assert sha(old_path) == bound['evidence/anchors_v2/build.json']
    report['input_sha256'].update({str(old_path): sha(old_path), str(manifest_path): sha(manifest_path)})
    old = json.loads(old_path.read_text(encoding='utf-8'))
    audio, provenance = read(args.workspace, 'A_exterior_blips', 'exterior_dynamic_observation')
    report['source'] = provenance
    report['input_sha256'][str(args.workspace/provenance['master'])] = provenance['master_sha256']
    report['input_sha256'][str(args.workspace/'references/segments_v1.json')] = provenance['catalog_sha256']
    index = repo/'voices/exterior_anchors_v1/index.json'
    model_index = json.loads(index.read_text(encoding='utf-8'))
    report['input_sha256'][str(index)] = sha(index)
    actual_models = []
    (args.out/'models').mkdir()
    for row in model_index['voices']:
        path = index.parent/row['file']
        assert sha(path) == row['model_sha256']
        report['input_sha256'][str(path)] = sha(path)
        target_path = args.out/'models'/path.name
        shutil.copy2(path, target_path)
        actual_models.append(target_path)
    # Reuse frozen observed peak paths, including their limitations. No new clock
    # refit, interpolation across missing passages, RPM conversion, or load labels.
    cases = [('fall', '补油后的局部降转', 'fall', 238.36, 239.28),
             ('low', '驻车低转', 'idle_context', 243.90, 247.10)]
    cards = []
    for key, title, path_key, start, stop in cases:
        directory = args.out/key
        directory.mkdir()
        rows = old['paths'][path_key]['rows']
        times = np.array([row['seconds'] for row in rows])
        hz = np.array([row['root_hz'] for row in rows])
        assert times[0] <= start < stop <= times[-1]
        source_frames = np.arange(round(start*48000), round(stop*48000)+1)
        # Include original observed knots, not a new low-resolution sampling grid.
        points = np.unique(np.r_[source_frames[0], np.round(times[(times>start)&(times<stop)]*48000).astype(int), source_frames[-1]])
        roots = np.interp(points/48000, times, hz)
        schedule(directory/'trajectory.txt', points-points[0], roots)
        generated = invoke(directory/'trajectory.txt', directory/'C_source', actual_models)
        first = source_frames[0]-round(provenance['seconds'][0]*48000)
        reference = audio[first:first+len(generated)]
        assert len(reference) == len(generated)
        sf.write(directory/'reference_float.wav', reference, 48000, subtype='FLOAT')
        trace = np.genfromtxt(directory/'C_source.csv', delimiter=',', names=True)
        error = trace['actual_acoustic_hz']-trace['target_acoustic_hz']
        passage = dict(key=key, title=title, seconds=[start, stop], frames=len(generated),
                       acoustic_target_hz=[float(roots.min()), float(roots.max())],
                       root_tracking_RMS_hz=float(np.sqrt(np.mean(error**2))),
                       root_tracking_max_hz=float(abs(error).max()),
                       out_of_anchor_trace_rows=int(np.count_nonzero(trace['coverage'])),
                       reference_peak=float(abs(reference).max()), generated_peak=float(abs(generated).max()),
                       phase_clock_qualified=False, training_overlap=True, actual_RPM=None, pedal=None, load=None)
        for name, x in [('reference', reference), ('C_source', generated)]:
            fade = np.ones(len(x))
            fade[:240] = np.linspace(0, 1, 240)
            fade[-240:] = np.linspace(1, 0, 240)
            y = .5*x*fade[:, None]
            assert abs(y).max() < .95 and np.isfinite(y).all()
            path = directory/(name+'_review.wav')
            sf.write(path, y, 48000, subtype='PCM_24')
            command([args.ffmpeg, '-v', 'error', '-i', path, '-f', 'null', '-'])
            passage[name+'_review_sha256'] = sha(path)
            cards.append((title+' · '+('录音参考' if name == 'reference' else '当前 C 多锚点 DNA'),
                          '../references/analysis/state_passage_v1/'+args.out.name+'/'+key+'/'+path.name))
        report['passages'].append(passage)
    page = args.workspace/'research/驻车状态局部对照V1.html'
    # A repeat may only republish an identical review, never replace feedback
    # or silently change an existing listening baseline.
    body = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>驻车状态局部对照 V1</title><style>body{font:16px/1.6 system-ui;max-width:820px;margin:30px auto;padding:0 18px;background:#f4f5f5;color:#20272b}h1{font-size:25px}.card{background:white;border:1px solid #dce1e3;border-radius:8px;padding:12px 16px;margin:12px 0}audio{width:100%;height:42px}.note{font-size:14px;color:#52616b}</style>
<h1>驻车状态局部对照 V1</h1><p>先暂停其他发声窗口。这里检查驻车低转与补油降转时，现有多锚点 DNA 的声线和过渡。</p>
<p><strong>这是声源诊断。</strong> C 持续生成声音，跟随录音中观察到的近似声学音高；没有播放素材循环。低频／噪音／事件与驾驶状态包络未参与。</p>
<p class="note">局部降转 A 238.36–239.28s；低转 A 243.90–247.10s。四锚点也来自这段录音，属于训练片段内检查。音高路径尚未通过完整相位校验，不能作为真实 RPM／踏板／负载或完整补油动作的复刻。保留 C 原有18ms跟随，不反向补偿或接管驾驶控制。</p>'''
    for title, url in cards:
        body += '<div class="card"><strong>'+title+'</strong><audio controls preload="metadata" src="'+url+'"></audio></div>'
    body += '''<p class="note">共同0.5增益、5ms首尾淡化；没有逐条响度匹配、EQ、压缩或新高频补偿。真实录音含完整排气／环境，C仅DNA，差别也包含缺失声层。没有替换已认可的移动尾排DNA＋相干低频。四档驻车模型尚未获音色验收。</p><p><a href="状态素材与系统回放V1.html">启动／减速／换挡等素材与系统功能回放</a></p><script>document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>document.querySelectorAll('audio').forEach(b=>{if(a!==b)b.pause()})))</script></html>'''
    if page.exists():
        assert page.read_text(encoding='utf-8') == body.replace(args.out.name, 'run2'), 'Use a new page version for changed audio'
        # Keep the original run2 URLs if the actual four audio bytes are equal.
        old_review = args.out.parent/'run2'
        for _, relative in cards:
            suffix = Path(relative).parts[-2:]
            assert (args.out/Path(*suffix)).read_bytes() == (old_review/Path(*suffix)).read_bytes()
        body = page.read_text(encoding='utf-8')
    else:
        page.write_text(body, encoding='utf-8', newline='\n')
    shutil.copy2(page, args.out/'page.html')
    url = quote('http://127.0.0.1:8789/research/'+page.name, safe=':/')
    with urlopen(url, timeout=15) as response:
        assert response.status == 200 and response.read() == page.read_bytes()
    for _, relative in cards:
        path = args.out/Path(relative).parent.name/Path(relative).name
        with urlopen(urljoin(url, relative), timeout=15) as response:
            assert response.status == 200 and response.read() == path.read_bytes()
    report.update(result='source_host_technical_pass_only', HTTP_bytes_verified=True,
                  page=url, browser_interaction_checked=False, driver_state_calibrated=False,
                  limits=['Coarse observed acoustic paths; full phase-clock qualification previously failed',
                          'Training-passage diagnostic, not unseen state/engine generalization',
                          'Existing18ms source follower retained; no RPM/pedal/load inference',
                          'DNA only; no accepted moving-A LF, residual, auxiliary, event or spatial layers',
                          'Prior short device functioning proof remains separate; no new long-run or12speaker check'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(result=report['result'], controls=len(report['controls']), passages=report['passages'], page=report.get('page')), ensure_ascii=False))
