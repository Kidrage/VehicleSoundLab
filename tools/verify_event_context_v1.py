"""Check two-background contrasts using known levels and antiphase stereo."""
import argparse
import json
from pathlib import Path
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    from event_authoring.context import probe
    from event_authoring.audio import sha
    a.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,a.output/'executed_verification.py')
    t=np.arange(3*48000)/48000
    low=.1*np.sin(2*np.pi*100*t);high=.1*np.sin(2*np.pi*3000*t)
    x=low+high;x[52800:57600]=low[52800:57600]+2*high[52800:57600]
    x[72000:81600]*=.25
    source=a.output/'known-antiphase.wav';sf.write(source,np.column_stack((x,-x)),48000,subtype='DOUBLE')
    actual,_=probe(source,[1.1,1.2],dict(before=[.8,1.],after=[1.5,1.7]),dict(mode='band',low_hz=1200,high_hz=14000))
    expected_full=10*np.log10(2.5);expected_scope=20*np.log10(2)
    for row,extra in zip(actual['backgrounds'],(0.,20*np.log10(4))):
        assert abs(row['full_contrast_db']-expected_full-extra)<1e-10
        assert abs(row['scoped_contrast_db']-expected_scope-extra)<.01
    refused=False
    try:probe(source,[1.1,1.2],dict(overlap=[1.,1.15]))
    except ValueError:refused=True
    assert refused and not actual['fit_performed'] and not actual['physical_identity_confirmed']
    previous=json.loads(Path('E:/VehicleSoundLab/references/analysis/event_sources_v1/E_detail1/report.json').read_text(encoding='utf-8'))['rows'][0]
    real=json.loads(Path('E:/VehicleSoundLab/references/analysis/exhaust_return_v1/context1/report.json').read_text(encoding='utf-8'))
    assert abs(real['sample_peak_seconds']-previous['sample_peak'])<1e-12
    for row in real['backgrounds']:
        reference=previous['sides'][row['name']]
        assert abs(row['full_contrast_db']-reference['full_db'])<1e-12
        assert abs(row['scoped_contrast_db']-reference['scoped_db'])<1e-12
    for row in real['backgrounds']:
        target=previous['sides'][row['name']]
        assert abs(row['full_contrast_db']-target['full_db'])<1e-12
        assert abs(row['scoped_contrast_db']-target['scoped_db'])<1e-12
    files=[Path(__file__),Path(__file__).with_name('probe_event_context.py'),Path(__file__).with_name('event_authoring')/'context.py']
    for file in files:shutil.copy2(file,a.output/file.name)
    report=dict(result='passed',known_levels=actual,original_E_values_exact=True,
        antiphase_stereo_power_preserved=True,overlap_refused=True,no_fit_or_identity_inference=True,
        sources={p.name:sha(p) for p in files})
    (a.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='passed',original_E_values_exact=True,known_contrasts=True)))


if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        if '--output' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--output')+1]);folder.mkdir(parents=True,exist_ok=True)
            (folder/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
