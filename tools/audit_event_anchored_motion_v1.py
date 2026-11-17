"""Independent anchored graph and sparse moving-OSC diagnostic audit."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from audit_event_modal_projection_v1 import independent_bands
from research_archive_v1 import load,save,sha


def check_support(rows,result,settings,df):
    lo,hi=settings['band_hz'];times=np.array([r['centre_seconds'] for r in rows])
    anchor=int(np.argmin(abs(times-settings['anchor_seconds'])))
    inventories=[]
    for row in rows:
        inventories.append([(j,p['hz']) for j,p in enumerate(row['peaks']) if lo<=p['hz']<hi])
    start=[j for j,f in inventories[anchor] if abs(f-settings['anchor_hz'])<=35]
    assert result['anchor_frame']==anchor and result['anchor_candidates']==start
    if len(start)!=1:
        assert result['status']==('ambiguous_anchor' if start else 'absent_anchor') and not result['points']
        return
    expected={anchor:start[0]};term=[]
    for direction in [-1,1]:
        frame=anchor;peak=start[0]
        while 0<=frame+direction<len(rows):
            index=frame+direction
            radius=.5*df+2000*abs(times[index]-times[frame])
            hz=rows[frame]['peaks'][peak]['hz']
            candidates=[j for j,f in inventories[index] if hz-radius<=f<=hz+radius]
            if len(candidates)!=1:
                term.append('absent' if not candidates else 'ambiguous_forward');break
            j=candidates[0];frequency=rows[index]['peaks'][j]['hz']
            predecessors=[k for k,f in inventories[frame] if frequency-radius<=f<=frequency+radius]
            if predecessors!=[peak]:term.append('ambiguous_reverse');break
            expected[index]=j;frame=index;peak=j
        else:term.append('observation_boundary')
    assert [(p['frame'],p['peak']) for p in result['points']]==sorted(expected.items())
    assert [r['reason'] for r in result['terminations']]==term
    for point in result['points']:
        assert all(point[key]==value for key,value in rows[point['frame']]['peaks'][point['peak']].items())
    assert all(b['frame']==a['frame']+1 for a,b in zip(result['points'][:-1],result['points'][1:]))


def direct_phase(profile,frames):
    clock=np.arange(frames)/48000
    nodes=np.array(profile['seconds']);frequency=np.array(profile['frequencies_hz'])
    # Sum each segment's exact area independently, rather than selecting a
    # pre-integrated prefix as in the production motion primitive.
    cycles=np.zeros(frames)
    for j in range(len(nodes)-1):
        duration=nodes[j+1]-nodes[j]
        local=np.clip(clock-nodes[j],0,duration)
        cycles+=frequency[j]*local+.5*(frequency[j+1]-frequency[j])/duration*local*local
    return profile['initial_phase']+2*np.pi*cycles


def direct_design(profile,frames,knots):
    angle=direct_phase(profile,frames)
    clock=np.arange(frames)/48000
    seconds=np.linspace(0,profile['duration_seconds'],knots) if knots>1 else [0.]
    hats=np.column_stack([np.interp(clock,seconds,row) for row in np.eye(knots)])
    return np.column_stack([np.cos(angle)[:,None]*hats,np.sin(angle)[:,None]*hats])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/Path(__file__).name)
    report=dict(result='running',cases=[],projections=[],goal_complete=False,timbre_accepted=False)
    save(args.output/'report.json',report)
    try:
        original=load(args.input/'report.json');assert original['result']=='passed'
        for case in original['cases']:
            for item in case['resolutions']:
                path=args.input/case['id']/(item['id']+'.json')
                assert sha(path)==item['sha256']
                doc=load(path)
                observer=load(doc['inventory_document'])
                assert sha(doc['inventory_document'])==doc['inventory_sha256']
                check_support(observer['inventories'],doc['tracking'],doc['settings'],observer['frequency_bin_hz'])
                report['cases'].append(dict(source=case['id'],resolution=item['id'],status=doc['tracking']['status'],
                    points=len(doc['tracking']['points']),all_decisions_and_no_gap_verified=True))
            for item in case['projections']:
                folder=args.input/case['id']/item['id']
                doc=load(folder/'projection.json');assert sha(folder/'projection.json')==item['sha256']
                x,sr=sf.read(folder/'source.wav',always_2d=True);assert sr==48000
                binding=case['source']
                assert sha(binding['path'])==binding['sha256']
                with sf.SoundFile(binding['path']) as stream:
                    stream.seek(doc['first_source_frame']);raw=stream.read(len(x),always_2d=True)
                np.testing.assert_array_equal(x,raw)
                for model in doc['models']:
                    design=direct_design(model['profile'],len(x),model['amplitude_knots'])
                    coefficient=np.array(model['coefficients'])
                    harmonic,sr=sf.read(folder/(model['id']+'-projection.wav'),always_2d=True)
                    remainder,_=sf.read(folder/(model['id']+'-remainder.wav'),always_2d=True)
                    assert sr==48000
                    error=float(abs(design@coefficient-harmonic).max());assert error<2e-11
                    np.testing.assert_allclose(harmonic+remainder,x,atol=2e-15,rtol=1e-13)
                    bands=independent_bands(x,harmonic,remainder).mean(axis=0)
                    expected=np.array([[row[key] for row in model['bands']] for key in ['source','projection','remainder','cross']])
                    np.testing.assert_allclose(bands,expected,atol=2e-14,rtol=2e-11)
                    fraction=1-np.mean(remainder**2)/np.mean(x**2)
                    assert abs(fraction-model['energy']['explained_SSE_fraction'])<1e-12
                    report['projections'].append(dict(source=case['id'],support=item['id'],model=model['id'],
                        frames=len(x),independent_direct_error_FS=error,
                        projection_sha256=sha(folder/(model['id']+'-projection.wav')),
                        remainder_sha256=sha(folder/(model['id']+'-remainder.wav'))))
        report.update(result='passed',input_report_sha256=sha(args.input/'report.json'),
            no_runtime_voice_or_physical_identity_qualified=True)
    except Exception as error:
        report.update(result='failed',error=repr(error));save(args.output/'report.json',report);raise
    save(args.output/'report.json',report)
    print('all anchored decisions, direct moving carriers and signed saved-audio budgets audited',flush=True)


if __name__=='__main__':main()
