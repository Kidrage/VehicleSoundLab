"""Use the exact accepted moving-tailpipe context and unchanged dry pair."""
import json
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha


def read(workspace, repository):
    root = workspace/'baselines/coherent_low_v1'
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    hashes = {r['path']: r['sha256'] for r in manifest['files']}
    def bound(name):
        path = root/name
        assert sha(path) == hashes[name], name
        return path
    report = json.loads(bound('evidence/report.json').read_text(encoding='utf-8'))
    reference = workspace/'references/analysis/low_body_v1/unhighpassed_normalized_float.wav'
    assert sha(reference) == report['source']['normalized_reference_sha256']
    catalog = json.loads((workspace/'references/segments_v1.json').read_text(encoding='utf-8'))
    source = catalog['sources']['A']
    assert sha(workspace/source['master']) == source['master_sha256'] == report['source']['master_sha256']
    assert sha(workspace/source['raw']) == source['raw_sha256']
    accepted = json.loads((repository/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repository/'voices/dna_bank_v1/V10 Exterior.model') == accepted['dna_model_sha256']
    assert sha(repository/accepted['model']) == accepted['model_sha256']
    x, rate = sf.read(reference, always_2d=True)
    dna, dna_rate = sf.read(bound('evidence/raw/dna.wav'), always_2d=True)
    low, low_rate = sf.read(bound('evidence/raw/measured.wav'), always_2d=True)
    assert rate == dna_rate == low_rate == 48000
    assert x.shape[1] == 2 and dna.shape == (384000, 2)
    assert np.isfinite(x).all() and np.isfinite(dna).all() and np.isfinite(low).all()
    base = dna+accepted['low_scale']*low[:len(dna)]
    return x, base, dict(source='A', original_seconds=report['source']['original_seconds'],
        acoustic_root_hz=46.875, reference_frames=len(x), reference_sha256=sha(reference),
        baseline_manifest_sha256=sha(root/'manifest.json'), dna_sha256=sha(bound('evidence/raw/dna.wav')),
        low_sha256=sha(bound('evidence/raw/measured.wav')), low_scale=accepted['low_scale'],
        catalog_sha256=sha(workspace/'references/segments_v1.json'), raw_sha256=source['raw_sha256'],
        master_sha256=source['master_sha256'], reference_path=str(reference),
        scope='Accepted fixed moving-tailpipe context restored at its existing acoustic coordinate; mixed recording, no physical noise separation')
