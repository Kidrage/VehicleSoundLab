"""Known-first normalized coherent-source representation and accounting checks."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import numpy as np

from audit_event_modal_projection_v1 import independent_bands
from event_authoring.model import synth, randoms
from event_modal_projection.basis import design, training_mask
from event_modal_projection.project import fit, energy
from event_modal_projection.measure import budgets
from research_archive_v1 import save,sha


def snapshot(repo,out):
    names=[*sorted((repo/'tools/event_modal_projection').glob('*.py')),
        repo/'tools/event_modal_projection/README.md',repo/'research/event_modal_projection_v1_plan.json',
        repo/'tools/verify_event_modal_projection_v1.py',repo/'tools/audit_event_modal_projection_v1.py',
        repo/'tools/event_authoring/model.py',repo/'tools/native_projection_v1/budget.py']
    bindings={}
    for p in names:
        name=p.relative_to(repo)
        dest=out/'exact_sources'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest);bindings[name.as_posix()]=sha(p)
    return bindings


def known():
    modes=[dict(hz=f,end_hz=f*1.13,phase=p,amplitude=0.) for f,p in
           [(145.31,.2),(441.98,-.7),(730.31,1.2),(1064.51,.4)]]
    frames=19200
    a,spec=design(modes,frames,5,True,.22)
    rng=np.random.default_rng(178291)
    coeff=rng.normal(0,.07,size=(a.shape[1],1))
    mono=a@coeff
    source=np.column_stack((mono[:,0],-mono[:,0]))
    mask=training_mask(frames)
    h,r,c,report=fit(a,source)
    error=float(abs(h-source).max())
    assert error<2e-13 and report['max_normal_residual_FS']<2e-14
    np.testing.assert_allclose(c,np.column_stack((coeff[:,0],-coeff[:,0])),atol=2e-13)
    mh,mr,_,masked=fit(a,source,mask)
    assert abs(mh-source).max()<2e-13
    # Old amplitudes, including zeros, have no role in these normalized columns.
    amended=deepcopy(modes)
    for m in amended:m['amplitude']=4.
    np.testing.assert_array_equal(a,design(amended,frames,5,True,.22)[0])
    # Equivalent design-column units must not change the projection.
    scale=np.geomspace(1e-10,10,a.shape[1])
    sh,_,_,scaled=fit(a*scale,source)
    assert abs(sh-h).max()<2e-13
    # Prescribed residual is exactly orthogonal, not assumed to be physical noise.
    random=rng.normal(size=source.shape)
    nh,nr,_,_=fit(a,random)
    zh,zr,_,_=fit(a,nr)
    assert abs(zh).max()<2e-13
    mixed=source+.03*nr
    ph,pr,_,_=fit(a,mixed)
    assert abs(ph-source).max()<2e-13
    account=energy(mixed,ph,pr)
    assert abs(account['signed_cross_FS2'])<2e-14 and abs(account['balance_error_FS2'])<2e-14
    rows,curves=budgets(mixed,ph,pr)
    independent=independent_bands(mixed,ph,pr)
    for j,name in enumerate(('source','projection','remainder','cross')):
        np.testing.assert_allclose(curves[name],independent[:,j],atol=2e-14,rtol=2e-11)
    assert max(row['maximum_balance_error_FS2'] for row in rows)<2e-14
    # Antiphase channels have full power despite zero mono fold.
    assert np.mean(mixed.mean(axis=1)**2)<np.mean(mixed**2)
    antirows,_=budgets(source,h,r)
    assert sum(row['source'] for row in antirows)>.001
    # The nominal phase/sweep convention agrees with existing event synthesis.
    seed=27431;variation=1+.002*randoms(seed,1)[0]
    p=dict(gated=1,duration_seconds=.5,attack_seconds=0.,release_seconds=.025,
        sweep_seconds=.22,level=1.,bands=[],modes=deepcopy(modes))
    for i,m in enumerate(p['modes']):
        m.update(amplitude=.03*(i+1),decay_seconds=.3)
    nominal=deepcopy(p['modes'])
    for m in nominal:m['hz']*=variation;m['end_hz']*=variation
    legacy_design,_=design(nominal,frames,1,False,.22)
    oracle=legacy_design@np.array([m['amplitude'] for m in p['modes']])
    phase_error=float(abs(oracle-synth(p,seed=seed,seconds=frames/48000)).max())
    assert phase_error<1e-13
    refused=0
    duplicate=design([modes[0],modes[0]],frames,1,True)[0]
    for bad in (lambda:fit(duplicate,source),lambda:fit(a*np.nan,source),
                lambda:fit(a,source,np.zeros(frames,dtype=bool)),
                lambda:design(modes,frames,10),lambda:design([dict(hz=24000,end_hz=24000,phase=0)],frames)):
        try:bad()
        except ValueError:refused+=1
        else:raise AssertionError('Invalid or rank-deficient problem accepted')
    return dict(result='passed',known_direct_recovery_error_FS=error,
        known_legacy_phase_error_FS=phase_error,full_condition=report['condition'],
        masked_condition=masked['condition'],scaled_condition=scaled['condition'],
        normalized_zero_old_amplitude_independence=True,antiphase_power_retained=True,
        orthogonal_null_and_signed_global_energy=True,independent_fft_cross_accounting=True,
        invalid_or_rank_refusals=refused,goal_complete=False,timbre_accepted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    bindings=snapshot(Path(__file__).resolve().parents[1],out)
    save(out/'report.json',dict(result='running',source_bindings=bindings))
    try:report=known()
    except Exception as error:
        save(out/'report.json',dict(result='failed',error=repr(error),source_bindings=bindings))
        raise
    report['source_bindings']=bindings;save(out/'report.json',report)
    print('normalized OSC projection, conditioning, masked recovery and independent budgets pass',flush=True)


if __name__=='__main__':main()
