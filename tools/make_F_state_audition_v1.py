"""Prepare exact approved native source slices and a single-player usability page."""
import argparse
import html
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.F-state-audition/1', result='running', sources={}, clips=[],
    real_audio_read=True, audio_quality_accepted=False, model_exported=False, runtime_changed=False)
try:
    plan = load(repo/'research/F_state_audition_v1_plan.json')
    approval = load(repo/'research/approved_state_media_v1_plan.json')
    approved = {row['id']:row for row in approval['sources'] if row['approved']}
    for path in (Path(__file__), repo/'research/F_state_audition_v1_plan.json',
                 repo/'research/approved_state_media_v1_plan.json', repo/'research/state_media_v1_visual_review.json',
                 repo/'tools/drive_evidence_v1/sources.py'):
        relative = path.relative_to(repo)
        destination = args.out/'exact_sources'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report['sources'][relative.as_posix()] = sha(path)
    masters = {}
    for row in plan['clips']:
        key = row['source']
        assert key in approved
        if key not in masters:
            location = args.workspace/'references/analysis/state_media_v1'/(key+'_inspect1')
            inspected = load(location/'report.json')
            master = location/'native_reference.wav'
            assert sha(master) == inspected['decoded']['sha256']
            assert sha(args.workspace/inspected['input_file']) == inspected['input_sha256']
            audio, sample_rate = sf.read(master, dtype='float64', always_2d=True)
            assert sample_rate == 48000 and audio.shape[1] == 2
            masters[key] = (audio, master, inspected, sha(location/'report.json'))
        audio, master, inspected, inspection_sha = masters[key]
        first, stop = (0, len(audio)) if row['seconds'] is None else [round(t*48000) for t in row['seconds']]
        assert 0 <= first < stop <= len(audio)
        clip = audio[first:stop]
        filename = row['id']+'.wav'
        sf.write(args.out/filename, clip, 48000, subtype='FLOAT')
        decoded, rate = sf.read(args.out/filename, dtype='float64', always_2d=True)
        assert rate == 48000 and np.array_equal(clip, decoded)
        report['clips'].append(dict(**row, file=filename, frames=len(clip), actual_seconds=[first/48000, stop/48000],
            source_master=master.relative_to(args.workspace).as_posix(), source_master_sha256=inspected['decoded']['sha256'],
            original_encoded=inspected['input_file'], original_encoded_sha256=inspected['input_sha256'],
            inspection_report_sha256=inspection_sha, sha256=sha(args.out/filename),
            samples_exact=True, peak=float(abs(clip).max()), source_url=approved[key]['url']))
    options = ''.join('<option value="'+html.escape(row['file'], quote=True)+'">'+html.escape(row['title'])+'</option>'
                      for row in report['clips'])
    metadata = json.dumps({row['file']:row for row in report['clips']}, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>怠速与加速 · 原素材核查</title><style>
body{font:17px/1.65 system-ui,sans-serif;max-width:780px;margin:48px auto;padding:0 24px;background:#12171d;color:#e5ebf1}
h1{font-size:27px}select,audio{width:100%;margin:12px 0}select{padding:12px;background:#202b35;color:inherit;border:1px solid #52616e;border-radius:8px}
p{color:#becbd6}a{color:#9bcaff}.small{font-size:14px}button{font:inherit}
</style><h1>怠速与加速 · 原素材核查</h1><p>先听尾排怠速，再听车内加速。这里都是原录音，尚未生成新的音色。</p>
<label for="choice">片段</label><select id="choice">OPTIONS</select><audio id="player" controls preload="metadata"></audio>
<p id="note"></p><a id="origin" target="_blank" rel="noreferrer">查看原视频</a>
<p>关注：发动机机械细节是否清楚，有没有配乐／说话／风噪，以及机位移动造成的声音变化。</p>
<p class="small">原幅度、双声道、未清洗。播放器统一从50%音量开始；各片段没有单独补偿响度。F2与F3车型和录音位置不同，分别建档。</p>
<script>const clips=METADATA;const choice=document.getElementById('choice'),player=document.getElementById('player');
player.volume=.5;function change(){player.pause();const clip=clips[choice.value];player.src=clip.file;player.load();
document.getElementById('note').textContent=clip.note;document.getElementById('origin').href=clip.source_url;}
choice.value='F2_tailpipe.wav';choice.addEventListener('change',change);change();</script></html>'''
    (args.out/'index.html').write_text(page.replace('OPTIONS', options).replace('METADATA', metadata), encoding='utf-8', newline='\n')
    assert page.count('<audio ') == 1
    report.update(result='exact_native_source_clips_and_single_player_prepared_not_audio_quality_acceptance',
        html_sha256=sha(args.out/'index.html'), common_player_volume=.5,
        source_clips_downloaded_again=False, normalization=False, filtering=False, resampling=False,
        idle_acceleration_complete=False, moving35='held_unchanged', A_low_listening='original_question_pending')
    print(json.dumps(dict(result=report['result'], clips=len(report['clips']), samples_exact=True)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
