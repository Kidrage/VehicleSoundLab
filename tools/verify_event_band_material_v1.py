"""Verify actual C band balance/seed behavior for one scoped material candidate."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('review',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.audio import sha
    from event_authoring.native import Renderer,controls
    from event_authoring.model import synth
    from event_authoring.measure import spectrum
    repo=Path(__file__).resolve().parents[1];renderer=Renderer(repo)
    document=json.loads((a.review/'analysis/profile.json').read_text(encoding='utf-8'))
    assert document['fit']['scope_band_fit_qualified']
    reference=document['fit']['scope_band_fit'];duration=document['provenance']['last_frame']-document['provenance']['first_frame']
    rows=[]
    for seed in (27431,48271,90217,149921):
        values=controls(dict(seconds=.6,seed=seed));x,report=renderer.render(document['parameters'],document['kind'],values)
        expected=synth(document['parameters'],seconds=.6,seed=seed).astype(np.float32)
        expected=np.pad(expected,(0,len(x)-len(expected)));error=float(np.max(abs(x.astype(float)-expected)))
        assert error<2e-7 and report['peak']<1
        f,power=spectrum(x[:duration,None]);bands=[]
        for b in reference:
            lo,hi=b['hz'];measured=float(power[(f>=lo)&(f<hi)].sum()*(f[1]-f[0]))
            bands.append(dict(hz=b['hz'],target_power=b['target_power'],actual_C_power=measured,
                error_db=float(10*np.log10(max(measured,1e-30)/max(b['target_power'],1e-30)))))
        sf.write(a.output/f'seed_{seed}.wav',x,48000,subtype='FLOAT')
        rows.append(dict(seed=seed,independent_C_error=error,peak=report['peak'],bands=bands))
    report=dict(schema='vsl.event-band-material-verification/1',result='passed',hearing_accepted=False,
        physical_identity_confirmed=False,renderer_sha256=renderer.identity,
        source_profile_sha256=sha(a.review/'analysis/profile.json'),cases=rows,
        all_four_tested_seeds_within_3db=all(abs(b['error_db'])<=3 for r in rows for b in r['bands']),
        limitation='Four specific seeds verify finite C output, not all random sequences, naturalness or physical event identity.')
    shutil.copy2(__file__,a.output/'executed_verification.py')
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
