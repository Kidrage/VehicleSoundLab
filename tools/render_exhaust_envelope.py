"""Frozen-take fired-envelope auditions and explicit pre/post-filter probes."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from runtime_review import ROOT, sha, rms
from review_pairs import common_pair
from comparison_page import comparison_page
from reference_segments import read_segment
from prepare_exhaust_envelope import response
import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'renders/exhaust_envelope_v1'
PROBE = ROOT/'build-experiment-exhaust-envelope/Release/exhaust_envelope_probe.exe'
MODES = {'base': 0, 'half': 1, 'full': 2}
LABELS = {'base': '原声基线', 'half': '谱形调整 · 一半', 'full': '谱形调整 · 完整'}
CASES = {'low': ('1200 RPM · 低转', 'low_base'), 'mid': ('4000 RPM · 带载', 'mid_base'),
         'high': ('8000 RPM · 带载', 'high_base'), 'neutral': ('空挡补油与落转', 'neutral_base'),
         'lift': ('收油与恢复', 'lift_base'), 'drive': ('30 秒运动自动挡', 'drive_base'),
         'high_character': ('8000 RPM · 保留燃烧／机械各 65%', 'high_combined')}
OBJECTS = ['exhaust_left','exhaust_right','intake','body','mechanical','air_left','air_right','events','road','wind']


def run(args):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, check=True,
                            capture_output=True, text=True, timeout=90)
    return result.stdout


def read(path):
    x, sr = sf.read(path, always_2d=True)
    assert sr == 48000 and sf.info(path).subtype == 'FLOAT' and np.isfinite(x).all()
    return x


def main():
    if (OUT/'results.json').exists():
        raise SystemExit('Preserve completed exhaust_envelope_v1.')
    recipe = json.loads((OUT/'recipe.json').read_text())
    assert sha(ROOT/'experiments/exhaust_envelope_v1/recipe.inc') == recipe['generated_profile_sha256']
    native = json.loads((ROOT/'renders/v0.16.0/verification.json').read_text())
    commands, inputs = {}, {}
    for _, take in CASES.values():
        path = ROOT/f'renders/v0.16.0/{take}.vsltake'
        assert sha(path) == native['files'][path.name]
        inputs[str(path.relative_to(ROOT)).replace('\\', '/')] = sha(path)
    def render(case, tag):
        args = [PROBE, ROOT/f'renders/v0.16.0/{CASES[case][1]}.vsltake', OUT/f'{case}_{tag}', MODES[tag], 2]
        stdout = run(args)
        assert 'pass' in stdout
        return case+'_'+tag, dict(command=list(map(str, args)), stdout=stdout)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(render, case, tag) for case in CASES for tag in MODES]
        for job in as_completed(jobs):
            key, value = job.result();commands[key] = value
            print('rendered', key, flush=True)
    impulse = {}
    gains = np.array([p['gain_db'] for p in recipe['recipe']])
    for sr in [16000, 48000, 192000]:
        impulse[str(sr)] = {}
        for tag, mode in MODES.items():
            path = OUT/f'impulse_{sr}_{tag}.wav'
            run([PROBE, 'impulse', path, sr, mode])
            x, rate = sf.read(path, always_2d=True)
            assert rate == sr and len(x) == sr and np.array_equal(x[:, 0], x[:, 1])
            h = np.fft.rfft(x[:, 0]);hz = np.fft.rfftfreq(sr, 1/sr)
            expected = response(hz, gains*(mode*.5), sr)
            actual = 20*np.log10(np.maximum(abs(h), 1e-30))
            error = float(abs(actual-expected).max())
            assert error < 3e-6 and abs(actual).max() < 6 and abs(actual[hz <= 400]).max() < .35
            assert abs(x[-sr//10:]).max() == 0
            impulse[str(sr)][tag] = dict(sha256=sha(path), maximum_response_error_db=error,
                maximum_correction_db=float(abs(actual).max()), maximum_below400_correction_db=float(abs(actual[hz <= 400]).max()),
                dc_gain=float(x[:, 0].sum()), final_100ms_peak=float(abs(x[-sr//10:]).max()))
    pages, rows = {}, {}
    for case, (label, take) in CASES.items():
        arrays = [read(OUT/f'{case}_{tag}.wav') for tag in MODES]
        assert all(abs(x).max() < .95 for x in arrays)
        assert (OUT/f'{case}_base.wav').read_bytes() == (ROOT/f'renders/v0.16.0/{take}.wav').read_bytes()
        assert (OUT/f'{case}_base.csv').read_bytes() == (ROOT/f'renders/v0.16.0/{take}.csv').read_bytes()
        raw = read(OUT/f'{case}_base_fired_input.wav')
        assert np.array_equal(raw, read(OUT/f'{case}_base_fired_output.wav'))
        isolation = {}
        for tag in MODES:
            assert (OUT/f'{case}_{tag}.csv').read_bytes() == (OUT/f'{case}_base.csv').read_bytes()
            assert np.array_equal(raw, read(OUT/f'{case}_{tag}_fired_input.wav'))
            unchanged = []
            for obj in OBJECTS:
                if (OUT/f'{case}_{tag}_source_{obj}.wav').read_bytes() == (OUT/f'{case}_base_source_{obj}.wav').read_bytes():
                    unchanged.append(obj)
            assert set(OBJECTS)-{'exhaust_left','exhaust_right','body'} <= set(unchanged)
            output = read(OUT/f'{case}_{tag}_fired_output.wav')
            h = read(OUT/f'impulse_48000_{tag}.wav')[:, 0]
            checks = []
            for c, obj in enumerate(['exhaust_left', 'exhaust_right']):
                expected = fftconvolve(raw[:, c], h)[:len(raw)]
                maximum = float(abs(expected-output[:, c]).max())
                assert maximum < 3e-7
                base_source = read(OUT/f'{case}_base_source_{obj}.wav')[:, 0]
                source = read(OUT/f'{case}_{tag}_source_{obj}.wav')[:, 0]
                remainder = (source-output[:, c])-(base_source-raw[:, c])
                residual = float(abs(remainder).max())
                assert residual < 3e-7
                checks.append(dict(bank=obj, independent_convolution_maximum_error=maximum,
                                   unchanged_pumping_character_remainder_maximum_error=residual))
            isolation[tag] = dict(unchanged_sources=unchanged, bank_path_checks=checks)
        audition = common_pair(OUT, arrays, list(MODES), case)
        rows[case] = dict(take=take, commands={tag:commands[case+'_'+tag] for tag in MODES},
                          audition=audition, isolation=isolation, raw_mix_rms_dbfs={tag:rms(x) for tag,x in zip(MODES, arrays)})
        pages[case] = dict(label=label, takes={tag:'../renders/exhaust_envelope_v1/'+audition[tag]['file'] for tag in MODES},
                          gain_note=f'同一驾驶输入，三版共用固定增益 {audition["base"]["gain_db"]:+.2f} dB；保留实际电平差异。')
        if case in ['mid', 'high']:
            banks = [read(OUT/f'{case}_{tag}_fired_output.wav') for tag in MODES]
            solo = common_pair(OUT, banks, list(MODES), case+'_fired')
            rows[case]['fired_audition'] = solo
            pages[case+'_fired'] = dict(label=label+' · 燃烧排气两源独奏',
                takes={tag:'../renders/exhaust_envelope_v1/'+solo[tag]['file'] for tag in MODES},
                gain_note=f'左右是两个源对象，不代表耳朵位置；三版共用独奏增益 {solo["base"]["gain_db"]:+.2f} dB。')
    # One complete new bed validates the same explicit source/tap path.
    run([PROBE, ROOT/'renders/v0.16.0/high_base.vsltake', OUT/'high_full_714', 2, 12])
    for obj in OBJECTS:
        assert (OUT/f'high_full_714_source_{obj}.wav').read_bytes() == (OUT/f'high_full_source_{obj}.wav').read_bytes()
    for tap in ['input', 'output']:
        assert (OUT/f'high_full_714_fired_{tap}.wav').read_bytes() == (OUT/f'high_full_fired_{tap}.wav').read_bytes()
    assert (OUT/'high_full_714.csv').read_bytes() == (OUT/'high_full.csv').read_bytes()
    scene_path = OUT/'high_full_714_scene.json'
    scene = json.loads(scene_path.read_text());scene['base_dsp_version'] = scene.pop('dsp_version')
    scene['experiment'] = 'exhaust_envelope_v1 full; bounded engineering voicing, not measured target transfer'
    for obj in scene['objects']:
        path = __import__('pathlib').Path(obj['file']);obj['sha256'] = sha(path);obj['file'] = path.name
    scene_path.write_text(json.dumps(scene, indent=2), encoding='utf-8')
    reference = {}
    for name, identity, use in [('low','A_exterior_low_rev','exterior_spectral_observation'), ('blips','A_exterior_blips','exterior_dynamic_observation')]:
        x, sr, provenance = read_segment(identity, use)
        n = round(.005*sr);fade = np.ones(len(x));fade[:n] = .5-.5*np.cos(np.linspace(0, np.pi, n));fade[-n:] = fade[:n][::-1]
        path = OUT/f'reference_A_{name}.wav';sf.write(path, .5*x*fade[:, None], sr, subtype='PCM_24')
        reference[name] = dict(provenance=provenance, file=path.name, sha256=sha(path),
                              processing='Fixed0.5 gain(-6.0206dB),5ms cosine endpoints,PCM24; no HP,denoise,normalization or channel fold.')
    fig, ax = plt.subplots(figsize=(9, 4.5), constrained_layout=True)
    for tag in MODES:
        x = read(OUT/f'impulse_48000_{tag}.wav')[:, 0]
        h = np.fft.rfft(x);f = np.fft.rfftfreq(len(x), 1/48000)
        ax.semilogx(f[1:], 20*np.log10(abs(h[1:])), label=tag)
    ax.set(xlim=(40, 16000), ylim=(-3.2, 3.2), xlabel='Hz', ylabel='C measured gain / dB',
           title='Bounded fixed-Hz fired-exhaust voicing / same transfer for both objects')
    ax.legend();ax.grid(alpha=.2);fig.savefig(OUT/'response.png', dpi=160);plt.close(fig)
    page = comparison_page(title='主排气谱形 · 实验 1', version='FIRED ENVELOPE 1 · EXPERIMENT',
        headline='比较燃烧主声线的厚度与锐度',
        intro='<p>先听 4000／8000 RPM，在原声、一半和完整调整之间切换。此轮只改燃烧排气支路的宽频谱形，泵气、机械、气流和回火保持独立。</p>',
        cases=pages, methods=LABELS,
        extra='<p>关注电子感、中频鼻音、排气厚度和高转声线是否变钝。曲线最大变化约 2.22 dB；这是受参考启发的有限音色尝试，原生 V016 配方未改。静态滤波没有新增逐次随机细节，亦包含自身因果相位响应。</p><details><summary>已批准车外参考（工况、录音和增益未匹配）</summary><p>低转</p><audio data-reference controls preload="metadata" src="../renders/exhaust_envelope_v1/reference_A_low.wav"></audio><p>补油</p><audio data-reference controls preload="metadata" src="../renders/exhaust_envelope_v1/reference_A_blips.wav"></audio></details>',
        footer='<p><a href="主排气谱形实验V1.md">配方、信号链与验证</a></p>')
    (ROOT/'research/主排气谱形试听V1.html').write_text(page, encoding='utf-8')
    result = dict(experiment='exhaust_envelope_v1', runtime='0.16.0 unchanged', seed=48271,
        recipe_sha256=sha(OUT/'recipe.json'), inputs=inputs, cases=rows, impulse=impulse, references=reference,
        stereo_714_sources_taps_trace_match=True,
        mechanism='Per-instance three-bell causal EQ on gated fired pressure only, before independent pumping/character and original IR return. No new OSC/noise/allpass/detune/source playback.',
        subjective='Unaccepted reference-informed bounded engineering voicing, not a measured manifold or realism result.',
        binaries={str(PROBE.relative_to(ROOT)).replace('\\','/'):sha(PROBE), 'build-v016/Release/vsl_core.lib':sha(ROOT/'build-v016/Release/vsl_core.lib')})
    result['files'] = {p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}
    (OUT/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('Envelope comparison: 21 full mixes,6 fired-source auditions,9 measured impulses; all isolation/convolution/714 checks pass.', flush=True)


if __name__ == '__main__':
    main()
