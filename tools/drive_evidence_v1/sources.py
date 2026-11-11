"""Read approved stereo observations using an explicit data workspace."""
import hashlib
import json
from pathlib import Path
import soundfile as sf


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(workspace, segment_id, use):
    catalog_path = workspace / 'references/segments_v1.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    assert catalog['schema'] == 'vsl.reference-segments/1'
    segment = catalog['segments'][segment_id]
    assert use in segment['allowed_uses']
    source = catalog['sources'][segment['source']]
    for key in ('raw', 'master'):
        assert sha(workspace / source[key]) == source[key + '_sha256']
    with sf.SoundFile(workspace / source['master']) as stream:
        assert stream.samplerate == 48000 and stream.channels == 2 and stream.subtype == 'FLOAT'
        first, stop = [round(t * stream.samplerate) for t in segment['seconds']]
        stream.seek(first)
        audio = stream.read(stop - first, always_2d=True, dtype='float64')
    return audio, dict(segment_id=segment_id, source=segment['source'],
        catalog_sha256=sha(catalog_path), master=source['master'],
        master_sha256=source['master_sha256'], raw_sha256=source['raw_sha256'],
        seconds=segment['seconds'], perspective=segment['perspective'],
        processing='Unchanged decoded stereo float samples; no filtering or gain',
        not_established=segment['not_established'])
