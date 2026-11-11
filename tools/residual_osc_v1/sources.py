"""Read only manifest-bound A/E anchor observations and frozen C renders."""
import json
from fractions import Fraction
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha

CASES = {
    'A_exterior':('exterior_anchors_v1','anchors_v2/A Stationary Upper Mid','normalized_float.wav',
                  'exterior_anchors_v1','A Stationary Upper Mid'),
    'E_cabin':('drive_evidence_v1','cabin_anchors_tapered/E Cabin Lower','normalized_reference_float.wav',
               'cabin_anchors_v1','E Cabin Lower')}


def read(workspace, repository, identity):
    baseline, subdir, normalized_name, bank_name, model_name = CASES[identity]
    root=workspace/'baselines'/baseline
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    prefix='evidence/'+subdir+'/'
    def bound(name):
        path=root/(prefix+name)
        expected=next(r for r in manifest['files'] if r['path']==prefix+name)['sha256']
        assert sha(path)==expected
        return path
    profile=bound('voice.model')
    normalized=bound(normalized_name)
    bank=repository/'voices'/bank_name
    index=json.loads((bank/'index.json').read_text(encoding='utf-8'))
    record=next(r for r in index['voices'] if r['name']==model_name)
    assert sha(profile)==sha(bank/record['file'])==record['model_sha256']
    hz=record['base_hz']
    audio,rate=sf.read(normalized,always_2d=True)
    assert rate==48000 and audio.shape[1]==2 and np.isfinite(audio).all()
    ratio=Fraction(46.875/hz).limit_denominator(10000)
    fixed=signal.resample_poly(audio,ratio.numerator,ratio.denominator,axis=0,window=('kaiser',8.6))
    renders={}
    for pitch in (.9,1.,1.1):
        path=bound(f'raw_{pitch:.1f}.wav')
        x,rate=sf.read(path,always_2d=True)
        assert rate==48000 and x.shape==(384000,2) and np.isfinite(x).all()
        renders[str(pitch)]=(x,path)
    return fixed,renders,dict(identity=identity,baseline=baseline,manifest_sha256=sha(root/'manifest.json'),
        normalized_source=str(normalized),normalized_sha256=sha(normalized),model_sha256=sha(profile),
        base_hz=hz,perspective=record.get('perspective','stationary exterior rear'),
        processing='Frozen normalized L/R observation restored to its anchor root; no gain/EQ/compression/channel folding',
        scope='One acoustic anchor; not measured RPM/load/state or an isolated physical noise recording')
