"""Versioned approved reference reader. No implicit cleaning, gain or mono mix."""
import json
from functools import lru_cache
from runtime_review import ROOT, sha
import soundfile as sf

CATALOG = ROOT / 'references/segments_v1.json'


@lru_cache(maxsize=1)
def catalog():
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if data['schema'] != 'vsl.reference-segments/1':
        raise ValueError('Unsupported segment schema')
    return data


@lru_cache(maxsize=None)
def checked_source(identity):
    source = catalog()['sources'][identity]
    for key in ['raw', 'master']:
        if sha(ROOT / source[key]) != source[key + '_sha256']:
            raise ValueError(f'Changed reference {identity}: {key}')
    info = sf.info(ROOT / source['master'])
    if info.channels != 2 or info.subtype != 'FLOAT':
        raise ValueError('Keep approved float32 stereo masters')
    return source


def read_segment(name, use):
    segment = catalog()['segments'][name]
    if use not in segment['allowed_uses']:
        raise ValueError(f'{name} is not catalogued for {use}')
    source = checked_source(segment['source'])
    path = ROOT / source['master']
    with sf.SoundFile(path) as file:
        rate = file.samplerate
        first, stop = [round(t * rate) for t in segment['seconds']]
        if not 0 <= first < stop <= len(file):
            raise ValueError('Invalid reference bounds')
        file.seek(first)
        audio = file.read(stop-first, always_2d=True, dtype='float64')
    provenance = dict(segment_id=name, catalog=str(CATALOG.relative_to(ROOT)),
        catalog_sha256=sha(CATALOG), source=segment['source'],
        master=source['master'], master_sha256=source['master_sha256'],
        source_seconds=segment['seconds'], frames=[first, stop], sample_rate=rate,
        channels=2, processing='None: unchanged L/R decoded float samples',
        not_established=segment['not_established'])
    return audio, rate, provenance
