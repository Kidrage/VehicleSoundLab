"""Compare repeated, pitch-matched rising/falling OSC spectra in one A context."""
import argparse,json,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--clocks',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read,sha
from state_dna_v1.compare import describe

from state_colour_v2.features import BANDS, shape_delta, select_windows

def run():
    args.out.mkdir(parents=True,exist_ok=False)
    x,source=read(args.workspace,'A_exterior_revs_extended','exterior_dynamic_observation')
    clocks=json.loads((args.clocks/'report.json').read_text(encoding='utf-8'))
    assert clocks['source']['master_sha256']==source['master_sha256'] and clocks['source']['catalog_sha256']==source['catalog_sha256']
    report=dict(schema='vsl.state-colour-repeats/1',source=source,clocks_sha256=sha(args.clocks/'report.json'),cases={},pairs=[],excluded=[],
        root_bin_hz=[45,50],bands_at_reference_root_hz=BANDS,reference_root_hz=46.875,
        limits=['Acoustic rise/fall, not measured driver load/pedal/fuel state',
            'Same video rear context, unknown mic transfer and audiovisual alignment',
            'Each passage is the replication unit; overlapping windows are not independent',
            'Mean harmonic power colour only; phase and inter-harmonic residual are separate'])
    for name,paths in clocks['cases'].items():
        path=paths['5'];rows=path['rows']
        if not rows:report['excluded'].append(dict(case=name,reason='No connected gated reference5 path'));continue
        times=np.array([r['seconds'] for r in rows]);roots=np.array([r['root_hz'] for r in rows])
        out=args.out/name;out.mkdir()
        try:y,where,evidence,z=describe(x,source['seconds'][0],times,roots,float(times[0]),float(times[-1]))
        except ValueError as e:report['excluded'].append(dict(case=name,reason=str(e)));continue
        center=np.asarray(evidence['window_root_hz']);keep=select_windows(evidence,name.startswith('rise'))
        evidence['selected_windows']=int(keep.sum())
        evidence['selected_root_hz']=center[keep].tolist()
        evidence['direction_rule']='Positive/negative local acoustic-root derivative at four-cycle window centre'
        evidence['independent_reference10_path']=paths['10']['status']
        selected=np.flatnonzero(keep)
        # Independent nonoverlap upper bound from actual four-cycle start offsets.
        disjoint=[]
        for k in selected:
            if not disjoint or k-disjoint[-1]>=16:disjoint.append(int(k))
        evidence['selected_nonoverlapping_window_count']=len(disjoint)
        if len(selected):
            evidence['mean_power_LR']=np.mean(abs(z[keep])**2,axis=0).tolist()
            evidence['selected_source_seconds']=np.asarray(evidence['window_source_seconds'])[keep].tolist()
        sf.write(out/'normalized.wav',y,48000,subtype='FLOAT')
        np.savez_compressed(out/'coordinates.npz',complex_rows=z,source_seconds=where,selected=keep)
        report['cases'][name]=evidence
        print(name,'cycles',round(evidence['normalized_cycles'],2),'selected',len(selected),'nonoverlap',len(disjoint),'supported',round(evidence['supported_hz_at_reference_root']),flush=True)
    for i in range(1,5):
        a,b=report['cases'].get('fall'+str(i)),report['cases'].get('rise'+str(i))
        if not(a and b and a['selected_windows'] and b['selected_windows']):continue
        pa,pb=np.array(a['mean_power_LR']),np.array(b['mean_power_LR'])
        delta=shape_delta(pa,pb)
        report['pairs'].append(dict(id=i,rise_minus_fall_shape_db_LR=delta.tolist(),
            rise_root_mean=float(np.mean(b['selected_root_hz'])),fall_root_mean=float(np.mean(a['selected_root_hz'])),
            common_supported_hz=min(a['supported_hz_at_reference_root'],b['supported_hz_at_reference_root'])))
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    for pair in report['pairs']:
        ax.plot(np.arange(5),np.array(pair['rise_minus_fall_shape_db_LR']).mean(axis=1),'o-',label='passage pair'+str(pair['id']))
    ax.set(xticks=range(5),xticklabels=[f'{a}-{b}' for a,b in BANDS],ylabel='Rise minus fall shape dB; scalar removed over28..6000Hz',xlabel='Hz at common acoustic root46.875')
    ax.grid(alpha=.2);ax.legend();fig.savefig(args.out/'repeat_shape.png',dpi=140);plt.close(fig)
    repo=Path(__file__).resolve().parents[1]
    report['source_sha256']={p.relative_to(repo).as_posix():sha(p) for p in [Path(__file__),repo/'tools/state_colour_v2/features.py',repo/'tools/state_dna_v1/compare.py',repo/'tools/exterior_clock_v1/warp.py',repo/'tools/sound_dna/windowed.py']}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('paired passages',len(report['pairs']))
if __name__=='__main__':run()
