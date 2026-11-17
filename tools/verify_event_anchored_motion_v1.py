"""Known-first anchored support and sparse continuous-phase OSC checks."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from audit_event_anchored_motion_v1 import check_support,direct_phase,direct_design
from event_local_structure.inspect import inspect
from event_anchored_motion.track import follow
from event_anchored_motion.motion import phase,design,validate
from event_modal_projection.project import fit
from research_archive_v1 import save,sha


def known(out):
    frames=57600;t=np.arange(frames)/48000
    stereo=lambda x:np.column_stack((x,.7*x))
    w=.9*2*np.pi
    smooth=stereo(.15*np.cos(2*np.pi*(600*t+200*(1-np.cos(w*t))/w)+.3))
    fixed=stereo(.15*np.cos(2*np.pi*600.31*t+.2))
    gap=fixed.copy();gap[(t>=.4)&(t<.65)]=0
    crossing=stereo(.12*np.cos(2*np.pi*(500*t+300*t*t))+.12*np.cos(2*np.pi*(1100*t-300*t*t)+.8))
    doublet=stereo(.1*np.cos(2*np.pi*600*t+.2)+.1*np.cos(2*np.pi*605*t+.4))
    rng=np.random.default_rng(149621)
    omega=2*np.pi*730.31/48000;alpha=np.sin(omega)/(2*100)
    noise=signal.lfilter(np.array([alpha,0,-alpha])/(1+alpha),
        [1,-2*np.cos(omega)/(1+alpha),(1-alpha)/(1+alpha)],rng.normal(size=frames+48000))[48000:]
    noise*=.12/np.sqrt(np.mean(noise**2))
    fixtures=dict(fixed=fixed,nonmonotonic=smooth,positive_AM=fixed*(.35+.65*np.sin(3*np.pi*t)**2)[:,None],
        gap=gap,crossing=crossing,unresolved_doublet=doublet,stochastic_resonance=stereo(noise))
    np.savez_compressed(out/'fixtures.npz',**fixtures)
    report=dict(result='running',observations=[],goal_complete=False,timbre_accepted=False)
    for name,x in fixtures.items():
        for n in (1536,3072):
            observed,_=inspect(x,n,n//4)
            anchor=730.31 if name=='stochastic_resonance' else (600+200*np.sin(w*.096) if name=='nonmonotonic' else (500+600*.096 if name=='crossing' else 600.31))
            settings=dict(anchor_seconds=.096,anchor_hz=float(anchor),band_hz=[300,1400])
            result=follow(observed['inventories'],48000/n,**settings)
            check_support(observed['inventories'],result,settings,48000/n)
            points=result['points'];assert points,(name,n,result)
            if name in ('fixed','positive_AM','nonmonotonic'):
                assert len(points)==len(observed['inventories']),(name,n,result['terminations'])
            if name=='fixed':
                assert max(abs(p['hz']-600.31) for p in points)<.04*48000/n
            if name=='gap':
                assert max(p['centre_seconds'] for p in points)<.65
                assert any(row['reason']!='observation_boundary' for row in result['terminations'])
            if name=='crossing':
                assert max(p['centre_seconds'] for p in points)<.8,(name,n,result['terminations'])
            report['observations'].append(dict(fixture=name,window_frames=n,points=len(points),
                support_seconds=[points[0]['centre_seconds'],points[-1]['centre_seconds']],
                terminations=result['terminations'],physical_identity_qualified=False,
                unresolved_or_stochastic_confound=name in ('unresolved_doublet','stochastic_resonance')))
            print(name,n,len(points),result['terminations'][-1]['reason'],flush=True)
    observed,_=inspect(fixed,1536,384)
    gain,_=inspect(fixed*.001,1536,384)
    one=follow(observed['inventories'],31.25,.096,600.31,[300,1400])
    two=follow(gain['inventories'],31.25,.096,600.31,[300,1400])
    assert [(p['frame'],p['peak']) for p in one['points']]==[(p['frame'],p['peak']) for p in two['points']]
    mono=fixed[:,0];anti,_=inspect(np.column_stack((mono,-mono)),1536,384)
    opposite=follow(anti['inventories'],31.25,.096,600.31,[300,1400])
    assert len(opposite['points'])==len(one['points'])
    for p in opposite['points']:assert abs(abs(p['LR_relative_phase_cycles'])-.5)<1e-12
    absent=follow(observed['inventories'],31.25,.096,1000,[300,1400]);assert absent['status']=='absent_anchor'
    manual=deepcopy(observed['inventories'][:3])
    for row in manual:row['peaks']=[dict(hz=600.),dict(hz=620.)]
    ambiguous=follow(manual,31.25,manual[1]['centre_seconds'],610,[300,1400]);assert ambiguous['status']=='ambiguous_anchor'
    profile=dict(schema='vsl.sparse-acoustic-motion/1',duration_seconds=1.2,
        seconds=[0.,.18,.4,.75,1.2],frequencies_hz=[600.,650.,450.,900.,700.],initial_phase=.3)
    p=phase(profile,frames)
    np.testing.assert_allclose(p,direct_phase(profile,frames),atol=4e-12,rtol=2e-14)
    chunks=np.concatenate([phase(profile,min(997,frames-first),first_frame=first) for first in range(0,frames,997)])
    np.testing.assert_array_equal(chunks,p)
    pitched=phase(profile,frames,pitch=1.1)
    np.testing.assert_allclose(pitched,.3+1.1*(p-.3),atol=4e-12,rtol=2e-14)
    constant=deepcopy(profile);constant['frequencies_hz']=[600.]*5
    np.testing.assert_allclose(phase(constant,frames,time_scale=1.1),.3+2*np.pi*600*t,atol=4e-12,rtol=2e-14)
    linear=dict(schema=profile['schema'],duration_seconds=1.2,seconds=[0.,1.2],frequencies_hz=[400.,1000.],initial_phase=.2)
    np.testing.assert_allclose(phase(linear,frames),.2+2*np.pi*(400*t+250*t*t),atol=4e-12,rtol=2e-14)
    a,_=design(profile,frames,5);oracle=direct_design(profile,frames,5)
    np.testing.assert_allclose(a,oracle,atol=4e-12,rtol=2e-11)
    coefficients=rng.normal(0,.1,(10,2));source=a@coefficients
    h,r,fitc,fitinfo=fit(a,source)
    assert abs(h-source).max()<1e-12
    np.testing.assert_allclose(fitc,coefficients,atol=1e-12)
    invalid=0
    bad=deepcopy(profile);bad['seconds'][1]=0
    for call in (lambda:validate(bad),lambda:phase(profile,frames,pitch=100),lambda:phase(profile,frames+2),
                 lambda:phase(profile,10,time_scale=0),lambda:follow([],31.25,.096,600,[300,1400])):
        try:call()
        except ValueError:invalid+=1
        else:raise AssertionError('Invalid motion/anchor input accepted')
    report.update(result='passed',gain_and_antiphase_preserved=True,explicit_absent_and_ambiguous_anchor=True,
        independent_graph_decisions=True,no_gap_reseed=True,motion_closed_form_and_block_prefix_exact=True,
        independent_motion_projection_error_FS=float(abs(h-source).max()),known_projection_condition=fitinfo['condition'],
        invalid_inputs_refused=invalid,unresolved_doublet_and_narrow_noise_not_physical_classifiers=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    sources=[*sorted((repo/'tools/event_anchored_motion').glob('*.py')),
        repo/'tools/event_anchored_motion/README.md',repo/'research/event_anchored_motion_v1_plan.json',
        Path(__file__),repo/'tools/audit_event_anchored_motion_v1.py',
        *sorted((repo/'tools/event_local_structure').glob('*.py')),
        repo/'tools/event_modal_projection/project.py',repo/'tools/audit_event_modal_projection_v1.py']
    bindings={}
    for source in sources:
        name=source.relative_to(repo);dest=out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);bindings[name.as_posix()]=sha(source)
    save(out/'report.json',dict(result='running',source_bindings=bindings))
    try:report=known(out)
    except Exception as error:
        save(out/'report.json',dict(result='failed',error=repr(error),source_bindings=bindings));raise
    report['source_bindings']=bindings;save(out/'report.json',report)
    print('known anchored support and independent continuous-phase motion checks pass',flush=True)


if __name__=='__main__':main()
