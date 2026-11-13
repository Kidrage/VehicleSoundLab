"""Replay original failed control unchanged; capture evidence at its assertion."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import save,sha
from accel_wideband_v1.checks import controls
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnosis.py');captured={}
def trace(frame,event,arg):
    if frame.f_code is controls.__code__:
        if event=='exception':
            captured.update(cases=frame.f_locals.get('out'),arrays=frame.f_locals.get('arrays'),line=frame.f_lineno)
        return trace
    return None
sys.settrace(trace)
try:
    controls()
except AssertionError:
    pass
else:
    raise AssertionError('Original failure no longer reproduced')
finally:
    sys.settrace(None)
assert captured['cases'] is not None and len(captured['cases'])==8
for name,arrays in captured['arrays'].items():np.savez_compressed(a.out/(name+'.npz'),**arrays)
moving=captured['cases']['moving_compensated'];native=captured['cases']['moving_native']
assert moving['high_true_matches']==native['high_true_matches']
report=dict(result='original_control_failure_reproduced_no_source_chirplet_analysis',
    original_source_sha256=sha(Path(controls.__code__.co_filename)),failed_line=captured['line'],
    cases=captured['cases'],reason='Native already recovers all known high lines; compensated count does not improve. Original gate not relaxed.',
    source_audio_read=False,qualification_passed=False)
# Preserve NumPy counts as ordinary JSON integers; the original source/gate is unchanged.
report=json.loads(json.dumps(report,default=lambda value:int(value)))
save(a.out/'report.json',report)
print({name:row['high_true_matches'] for name,row in captured['cases'].items()})
