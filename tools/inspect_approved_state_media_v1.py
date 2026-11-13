"""Decode approved new recordings at native rate and inspect coarse video/state context."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--fetch', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(args.workspace/'tools/python_deps'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import soundfile as sf
    from drive_evidence_v1.sources import sha
    from state_media_v1.measure import BANDS, recording_measurements
    from state_media_v1.frames import context_frames

    fetch = json.loads((args.fetch/'report.json').read_text(encoding='utf-8'))
    assert fetch['result'] == 'downloaded_for_usability_inspection'
    assert '批准 F1＋F2＋F3' in fetch['approval_evidence']
    media = args.workspace/fetch['file']
    assert sha(media) == fetch['sha256']
    args.out.resolve().relative_to((args.workspace/'references/analysis').resolve())
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='vsl.state-media-inspection/1', result='running',
        identity=fetch['identity'], fetch_report_sha256=sha(args.fetch/'report.json'),
        input_file=fetch['file'], input_sha256=sha(media), sources={},
        model_extracted=False, runtime_changed=False, timbre_accepted=False)
    try:
        paths = [Path(__file__), repo/'research/approved_state_media_v1_plan.json',
                 repo/'tools/drive_evidence_v1/sources.py', *sorted((repo/'tools/state_media_v1').glob('*.py'))]
        for source in paths:
            relative = source.relative_to(repo)
            target = args.out/'exact_sources'/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            report['sources'][relative.as_posix()] = sha(source)
        ffmpeg = Path('D:/repo/tools/ffmpeg/bin/ffmpeg.exe')
        command = [str(ffmpeg), '-hide_banner', '-nostdin', '-i', str(media), '-map', '0:a:0',
                   '-vn', '-c:a', 'pcm_f32le', str(args.out/'native_reference.wav')]
        result = subprocess.run(command, capture_output=True, check=True)
        (args.out/'decode_log.txt').write_bytes(result.stderr)
        audio, rate = sf.read(args.out/'native_reference.wav', dtype='float64', always_2d=True)
        assert (rate, audio.shape[1]) == (48000, 2)
        report['decoded'] = dict(command=command, file='native_reference.wav',
            sha256=sha(args.out/'native_reference.wav'), sample_rate=rate, channels=2,
            normalized=False, resampled=False, source='Lossy original Opus decoded once, not lossless source recovery')
        measurements, arrays = recording_measurements(audio, rate)
        np.savez_compressed(args.out/'recording_observations.npz', **arrays)
        report['measurements'] = measurements
        figure, axes = plt.subplots(3, 1, figsize=(13, 9), constrained_layout=True)
        axes[0].plot(arrays['rms_seconds'], 20*np.log10(np.maximum(arrays['rms_LR'], 1e-12)))
        axes[0].set(xlabel='Decoded audio seconds', ylabel='Quarter-second RMS dBFS',
                    title=fetch['identity']+' raw recording; no normalization, RPM/load inference or fitting')
        for index, (lo, hi) in enumerate(BANDS):
            axes[1].plot(arrays['seconds'], 10*np.log10(np.maximum(arrays['band_power_LR'][:, index].mean(axis=0), 1e-30)),
                         label=f'{lo}..{hi} Hz')
        axes[1].set(xlabel='Decoded audio seconds', ylabel='Mixed recording band power dBFS')
        axes[1].legend(ncol=4, fontsize=8)
        axes[2].semilogx(arrays['hz'][1:], 10*np.log10(np.maximum(arrays['mean_psd_LR'][:, 1:].T, 1e-30)))
        axes[2].set(xlim=(20, 20000), xlabel='Frequency Hz', ylabel='Mean PSD dBFS/Hz')
        figure.savefig(args.out/'recording_observations.png', dpi=125)
        plt.close(figure)
        probe = json.loads((args.fetch/'ffprobe.json').read_text(encoding='utf-8'))
        stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        count = {'F1': 12, 'F2': 8, 'F3': 24}[fetch['identity']]
        report['context'] = context_frames(media, args.out, stream, fetch['duration_seconds'], count, ffmpeg)
        for row in report['context']['frames']:
            row['sha256'] = sha(args.out/row['file'])
        report.update(result='raw_recording_measured_and_coarse_video_prepared',
            context_sheet='context.jpg', context_sheet_sha256=sha(args.out/'context.jpg'),
            plot_sha256=sha(args.out/'recording_observations.png'),
            visual_review_completed=False, audio_listening_completed=False,
            limits=['No new phase extractor or DNA model is qualified by these recording-level observations',
                'Video PTS and decoded audio zero are recorded separately; AV delay not calibrated',
                'Visual context and listening must be assessed before choosing fitting intervals'])
    except Exception as exc:
        report.update(result='failed', error=repr(exc))
        raise
    finally:
        (args.out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                                          encoding='utf-8', newline='\n')
    print(json.dumps(dict(identity=fetch['identity'], result=report['result'],
                         frames=len(report['context']['frames'])), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
