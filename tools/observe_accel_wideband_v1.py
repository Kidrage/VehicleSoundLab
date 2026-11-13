"""All48 F3 coverage decompositions and guide-conditioned chirplet inventories."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_wideband_v1.coverage import oscillator_model,decomposition
from accel_wideband_v1.chirplet import transform,inventory,relative_rate
from accel_wideband_v1.checks import controls
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[])
try:
    plan_path=repo/'research/accel_wideband_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',*sorted((repo/'tools/accel_wideband_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    known,arrays=controls();save(a.out/'controls.json',known);(a.out/'known').mkdir()
    for name,values in arrays.items():np.savez_compressed(a.out/'known'/(name+'.npz'),**values)
    print(dict(known={k:v['high_true_matches'] for k,v in known['cases'].items()}),flush=True)
    parent=a.workspace/'baselines/accel_chirp_v1/evidence/observe1'
    for name in plan['segments']:
        rows=load(parent/name/'fits.json');folder=a.out/name;folder.mkdir();result=[]
        for i,row in enumerate(rows):
            original=parent/name/f'tile_{i:02d}.npz';saved=np.load(original);audio=saved['audio']
            all_model=oscillator_model(row);eligible_model=oscillator_model(row,eligible=True)
            assert abs(all_model-saved['reconstructed']).max()<1e-12
            # The parent residual's DC arithmetic grouping was already independently audited.
            all_parts,all_error=decomposition(audio,all_model,plan['bands_hz'])
            eligible_parts,eligible_error=decomposition(audio,eligible_model,plan['bands_hz'])
            alpha=relative_rate(rows,i);frequency,z=transform(audio,alpha)
            window=.5-.5*np.cos(2*np.pi*np.arange(len(audio))/len(audio))
            native=np.fft.rfft(audio*window[:,None],axis=0)[:len(frequency)]
            native*=np.exp(2j*np.pi*frequency*len(audio)/(2*48000))[:,None]
            arrays=dict(audio=audio,all_model=all_model,eligible_model=eligible_model,
                frequency=frequency,native_transform=native,compensated_transform=z)
            np.savez_compressed(folder/f'tile_{i:02d}.npz',**arrays)
            entry=dict(tile=i,parent_tile_sha256=sha(original),fit_success=row['success'],guide_supported=row['guide_supported'],
                candidate_alpha=alpha,all_line_count=len(row['lines']),eligible_line_count=sum(line['eligible'] for line in row['lines']),
                all_parts=all_parts,eligible_parts=eligible_parts,power_identity_error=max(all_error,eligible_error),
                native_inventory=inventory(frequency,native),compensated_inventory=inventory(frequency,z))
            result.append(entry)
            print(dict(segment=name,tile=i,alpha=alpha,native_high=entry['native_inventory']['counts']['high'],
                compensated_high=entry['compensated_inventory']['counts']['high'],guide_supported=row['guide_supported']),flush=True)
        save(folder/'report.json',dict(rows=result,parent_fits_sha256=sha(parent/name/'fits.json')))
        r['observations'].append(dict(segment=name,tiles=len(rows),native_high=sum(v['native_inventory']['counts']['high'] for v in result),
            compensated_high=sum(v['compensated_inventory']['counts']['high'] for v in result)))
        save(a.out/'report.json',r)
    r.update(result='native_coverage_and_conditional_wideband_inventories_complete',plan=plan,
        source_identity=False,engine_phase_qualified=False,profile_or_audio_exported=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],observations=r['observations']),flush=True)
