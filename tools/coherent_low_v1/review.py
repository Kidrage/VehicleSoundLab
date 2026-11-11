"""Render C-generated controls and write explicit gain-matched listening files."""
import html
import json
import subprocess
import numpy as np
import soundfile as sf
from scipy import signal
from .observation import sha


RATE = 48000


def rms(audio):
    return float(np.sqrt(np.mean(audio * audio)))


def band_rms(audio):
    sos = signal.butter(4, [25, 350], btype='bandpass', fs=RATE, output='sos')
    return rms(signal.sosfiltfilt(sos, audio, axis=0))


def render(probe, profile, target, seconds=8, pitch=1):
    command = [str(probe), str(profile), str(target), str(seconds), str(pitch), '1', '1']
    subprocess.run(command, check=True, capture_output=True, timeout=90)
    audio, rate = sf.read(target, always_2d=True)
    assert rate == RATE and len(audio) == round(seconds * RATE) and np.isfinite(audio).all()
    return audio, dict(command=command, sha256=sha(target))


def make(workspace, repository, output, probe, source):
    raw = output / 'raw'
    raw.mkdir()
    audition = output / 'audition'
    audition.mkdir()
    dna, dna_log = render(probe, repository / 'voices/dna_bank_v1/V10 Exterior.model', raw / 'dna.wav')
    frozen, rate = sf.read(workspace / 'references/analysis/low_rumble_v2/renders/A Exterior_DNA_raw.wav', always_2d=True)
    assert rate == RATE and np.array_equal(dna, frozen[:len(dna)])
    measured, measured_log = render(probe, output / 'models/measured_phase.model', raw / 'measured.wav', 16)
    scrambled, scrambled_log = render(probe, output / 'models/scrambled_phase.model', raw / 'scrambled.wav', 16)
    recordings = dict(measured=measured[:len(dna)], scrambled=scrambled[:len(dna)])
    for name, path in [('old_three', 'low_body_v1/renders/bass100_body_float.wav'),
                       ('old_v2', 'low_rumble_v2/renders/A Exterior_low_raw.wav')]:
        audio, rate = sf.read(workspace / 'references/analysis' / path, always_2d=True)
        assert rate == RATE and len(audio) >= len(dna)
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        recordings[name] = audio[:len(dna)]
    records = {}
    fade = np.ones(len(dna))
    fade[:240] = np.linspace(0, 1, 240)
    fade[-240:] = np.linspace(1, 0, 240)

    def save(name, audio):
        audio = audio * .5 * fade[:, None]
        assert np.max(abs(audio)) < .95
        path = audition / (name + '.wav')
        sf.write(path, audio, RATE, subtype='PCM_24')
        records[name] = dict(file='audition/' + path.name, frames=len(audio), sha256=sha(path),
                             peak=float(np.max(abs(audio))), rms=rms(audio))

    save('dna_only', dna)
    matching = {}
    for name, audio in recordings.items():
        gain = .065 / band_rms(audio)
        low = audio * gain
        matching[name] = dict(gain=gain, gain_db=float(20 * np.log10(gain)),
                              original_band_rms=band_rms(audio), matched_band_rms=band_rms(low))
        save(name + '_solo', low)
        save(name + '_mix', dna + low)
        if name == 'measured':
            save('measured_half_mix', dna + .5 * low)
    reference = signal.sosfiltfilt(signal.butter(4, [25, 350], btype='bandpass', fs=RATE, output='sos'), source, axis=0)
    reference_path = audition / 'normalized_recording_low.wav'
    sf.write(reference_path, reference * .5, RATE, subtype='PCM_24')
    for pitch in (.9, 1.1):
        render(probe, output / 'models/measured_phase.model', raw / f'pitch_{pitch}.wav', pitch=pitch)
    return dict(probe_sha256=sha(probe), dna=dna_log, measured=measured_log, scrambled=scrambled_log,
                accepted_DNA_float_equal=True, same_seed_phase_control=True,
                exact_repeated_8_second_blocks=bool(np.array_equal(measured[:8 * RATE], measured[8 * RATE:])),
                continued_variation_difference_rms=rms(measured[:8 * RATE] - measured[8 * RATE:]),
                output_duration_independent_of_pitch=True,
                low_matching=matching, files=records,
                gain_policy='Each LF stem matched to 0.065 RMS after offline 25..350Hz measurement; unchanged DNA, all mixes use common 0.5 output gain, 5ms edge fades; no whole-mix normalization or brightening',
                seed_limit='Probe initializes each independent voice with seed48271; LF and DNA random states are separate but seed derivation has not been integrated into a multi-voice real-time host')


def write_page(workspace, output):
    prefix = '../references/analysis/' + output.name + '/audition/'
    groups = [
        ('完整混音', [('dna_only', '只听认可 DNA'), ('measured_half_mix', '实测相位 · 低频50%'),
                   ('measured_mix', '实测相位 · 低频100%'), ('scrambled_mix', '打散相位 · 低频100%')]),
        ('低频独奏：同一低频 RMS', [('measured_solo', '实测相位'), ('scrambled_solo', '打散相位'),
                                  ('old_three_solo', '旧三音'), ('old_v2_solo', '旧 V2 扩散声')])]
    sections = []
    for title, variants in groups:
        cards = ''.join(f'<div class="card"><label for="{key}">{html.escape(label)}</label>'
                        f'<audio id="{key}" controls preload="metadata" src="{prefix}{key}.wav"></audio></div>' for key, label in variants)
        sections.append(f'<section><h2>{title}</h2>{cards}</section>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<title>低频相干对照 V1</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:840px;margin:30px auto;padding:0 20px;background:#f4f5f5;color:#20272b}h1{font-size:25px}h2{font-size:19px}section{margin:26px 0}.card{padding:12px 16px;margin:10px 0;background:white;border:1px solid #dce1e3;border-radius:8px}label{display:block;margin-bottom:8px}audio{width:100%;height:42px}details{margin-top:28px;font-size:14px}p{max-width:70ch}</style>'
    page += '<h1>低频相干对照 V1</h1><p>先比较完整混音中的“实测相位”与“打散相位”，再比较低频独奏。关注发动机感、厚度、嗡鸣和颤动。</p><p>两种新低频使用同一幅度变化，仅改变各阶固定相位；各低频已匹配25–350Hz RMS。认可的 DNA 保持一致，混音使用相同输出增益。</p>'
    page += ''.join(sections)
    page += f'<details><summary>录音参考与本轮范围</summary><p>归一化音高的录音低频参考，约1.2秒；保留原数字电平，仅0.5输出增益，不与合成独奏匹配响度。</p><audio controls preload="metadata" src="{prefix}normalized_recording_low.wav"></audio><p>模型仅来自已批准A车外316.10–317.25秒。实测相位指相对此声线坐标的均值相位，并不等于已分离的物理发动机声源。相位稳定性因成分而异；相对第5阶是跟踪坐标依据，未作为独立验证。旧三音与V2还存在谱形差异，主要相位对照应在两种新候选之间进行。页面播放的是C持续生成后导出的片段，无原录音循环。</p></details>'
    page += '<script>document.querySelectorAll("audio").forEach(a=>a.addEventListener("play",()=>document.querySelectorAll("audio").forEach(b=>{if(b!==a)b.pause()})))</script></html>'
    path = workspace / 'research/低频相干对照V1.html'
    path.write_text(page, encoding='utf-8')
    return path
