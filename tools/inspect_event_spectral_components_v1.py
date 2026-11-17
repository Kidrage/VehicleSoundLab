"""Read-only finite modal/noise budget and bounded modal-capacity diagnostics."""
import argparse
from pathlib import Path
import shutil

import numpy as np
from scipy import linalg

from event_authoring.contour_response import QuadraticResponse
from event_authoring.response_fit import EDGES
from event_spectral_source.profile import TRAIN_SEEDS, vector
from event_spectral_source.voice import basis
from research_archive_v1 import load,save,sha


def group_maximum(gram):
    count=gram.shape[-1]
    vertices=8*((np.arange(1<<count)[:,None]>>np.arange(count)[None,:])&1)
    return np.max(np.einsum('vi,...ij,vj->...v',vertices,gram,vertices,optimize=True),axis=-1)


def verify_math():
    q=np.array([[1.,-.5],[-.5,2.]])
    assert group_maximum(q)==128.
    rng=np.random.default_rng(6381)
    wave=rng.normal(size=(4096,7))
    signs=linalg.hadamard(8)[:,1:7]
    mixed=wave[:,[0]]+wave[:,1:]@signs.T
    expected=np.mean(wave[:,0]**2)+np.mean(wave[:,1:]**2,axis=0).sum()
    assert abs(np.mean(mixed**2)-expected)<1e-13


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/Path(__file__).name)
    verify_math()
    fit=load(args.input/'report.json');assert fit['result']=='passed'
    rows=[]
    for c in fit['cases']:
        p=load(args.input/c['kind']/'candidate-before-validation.json')
        g=vector(p);extended=np.r_[g,1.]
        sizes=[len(group['gain']) for group in p['modal'].get('contours',[])]
        offsets=np.r_[0,np.cumsum(sizes)]
        modal_count=int(offsets[-1]);modal_index=np.r_[np.arange(modal_count),len(g)]
        targets=np.array([b['target_power'] for b in c['seeds'][0]['old']['bands']])
        seed_rows=[]
        for seed in TRAIN_SEEDS:
            wave=basis(p,c['observation_frames']/48000,seed)
            gram=QuadraticResponse._grams(wave,1024,EDGES).mean(axis=1)
            modal=extended[modal_index]@gram[:,modal_index][:,:,modal_index]@extended[modal_index]
            noise=[]
            for i in range(6):
                index=np.arange(modal_count+i*8,modal_count+(i+1)*8)
                noise.append(g[index]@gram[:,index][:,:,index]@g[index])
            noise=np.array(noise)
            full=extended@gram@extended
            cross=full-modal-noise.sum(axis=0)
            upper=np.sqrt(np.maximum(gram[:,-1,-1],0))
            for start,stop in zip(offsets[:-1],offsets[1:]):
                upper+=np.sqrt(np.maximum(group_maximum(gram[:,start:stop,start:stop]),0))
            upper=upper**2
            # Exact average over balanced signs removes inter-branch and
            # modal/noise cross power, keeping every within-branch term.
            signs=linalg.hadamard(8)[:,1:7]
            balanced=[]
            for sign in signs:
                value=extended.copy()
                for i in range(6):value[modal_count+i*8:modal_count+(i+1)*8]*=sign[i]
                balanced.append(value@gram@value)
            np.testing.assert_allclose(np.mean(balanced,axis=0),modal+noise.sum(axis=0),atol=2e-13,rtol=2e-11)
            seed_rows.append(dict(seed=seed,modal_power=modal.tolist(),noise_branch_powers=noise.tolist(),
                cross_power=cross.tolist(),full_power=full.tolist(),
                modal_to_target=(modal/targets).tolist(),cross_to_target=(cross/targets).tolist(),
                upper_bound_modal_power_under_current_gains=upper.tolist(),
                upper_bound_modal_to_target=(upper/targets).tolist()))
        rows.append(dict(kind=c['kind'],source_target_power=targets.tolist(),seeds=seed_rows,
            mean_modal_to_target=np.mean([r['modal_to_target'] for r in seed_rows],axis=0).tolist(),
            mean_cross_to_target=np.mean([r['cross_to_target'] for r in seed_rows],axis=0).tolist(),
            mean_upper_bound_modal_to_target=np.mean([r['upper_bound_modal_to_target'] for r in seed_rows],axis=0).tolist()))
    save(args.output/'report.json',dict(result='passed',reviewed_report=str(args.input/'report.json'),
        reviewed_report_sha256=sha(args.input/'report.json'),cases=rows,known_vertex_and_balanced_sign_controls=True,
        no_source_fit_candidate_or_gate_change=True,
        limitations='Algorithmic components are not isolated physical engine parts. The modal bound is a conservative '
            'Minkowski bound using exact convex box maxima per contour group, not a bound on a redesigned bank. '
            'Balanced signs are an exact finite mathematical diagnostic, not a fitted or accepted new voice.',
        goal_complete=False,timbre_accepted=False))
    print('finite component powers, signed cross terms and modal-capacity bounds recorded',flush=True)


if __name__=='__main__':main()
