"""Render audited relative-phase models, recording generation and time evidence."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('workspace', 'study', 'audit', 'out'):
        p.add_argument('--'+n, type=Path, required=True)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[n] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from relative_phase_v1.render import render_pair
    from relative_phase_v1.coordinates import decode
    from radial_copula_v1.latent import endpoints, independent_draws
    from radial_copula_v1.observe import describe, json_summary, lag_covariance
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', cases=[], sources={}, inputs={})
    try:
        study = load(a.study/'report.json'); audit = load(a.audit/'report.json')
        assert study['result'] == 'six_source_relative_phase_evidence_ready'
        assert audit['result'] == 'independent_relative_phase_audit_passed' and audit['producer_sha256'] == sha(a.study/'report.json')
        report['inputs'].update({str(p):sha(p) for p in [a.study/'report.json', a.audit/'report.json']})
        names = list(study['sources'])+['research/relative_phase_v1_audio_plan.json',
                  'tools/render_relative_phase_v1.py', 'tools/relative_phase_v1/render.py']
        for name in names:
            path=a.out/'exact_sources'/name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name,path); report['sources'][name]=sha(path)
        plan = load(repo/'research/relative_phase_v1_audio_plan.json')
        bands = load(repo/'research/relative_phase_v1_plan.json')['bands_Hz']
        for label in plan['anchors']:
            old = next(r for r in study['cases'] if r['label']==label)
            folder = a.out/label; folder.mkdir(); root = old['root_hz']
            source = a.study/label/'profile.npz'; assert sha(source)==old['profile_sha256']
            shutil.copy2(source,folder/'profile.npz'); report['inputs'][str(source)]=sha(source)
            model = dict(np.load(source)); training = a.study/label/'training.npz'
            report['inputs'][str(training)] = sha(training)
            values = np.load(training)['source_rows'].reshape(-1,288,2,2)
            z = values[...,0]+1j*values[...,1]
            measured = describe(abs(z),np.angle(z),root,bands)
            row = dict(label=label,root_hz=root,profile_sha256=sha(source),audio=[],temporal=[],
                       source=json_summary(measured),source_lag1_power_covariance=lag_covariance(measured['power']).tolist())
            report['cases'].append(row); save(a.out/'report.json',report)
            for seed in plan['seeds']:
                audio = render_pair(folder,model,root,plan['seconds'],seed,plan['block'])
                for clip in audio:
                    clip['sha256']=sha(folder/clip['file']); row['audio'].append(clip)
                count=audio[0]['texture_endpoints']; state,_=endpoints(model,count,seed)
                amplitude,phase=decode(model,independent_draws(model,state))
                moments=describe(amplitude,phase,root,bands)
                path=folder/f'temporal_{seed}.npz'
                np.savez_compressed(path,**moments,lag1_covariance=lag_covariance(moments['power']))
                row['temporal'].append(dict(seed=seed,sha256=sha(path),**json_summary(moments),
                    lag1_covariance=lag_covariance(moments['power']).tolist()))
                save(a.out/'report.json',report); print('Rendered paired OSC',label,seed,flush=True)
            if label==plan['anchors'][0]:
                copies=render_pair(folder,model,root,plan['seconds'],plan['seeds'][0],plan['identity_block'],'_block37')
                for clip in copies:
                    original=folder/f'{clip["variant"]}_{clip["seed"]}.wav'
                    assert np.array_equal(sf.read(original,always_2d=True)[0],sf.read(folder/clip['file'],always_2d=True)[0])
                    clip['sha256']=sha(folder/clip['file'])
                row['block37_copies']=copies; row['block37_1024_both_variants_PCM_exact']=True
        report.update(result='relative_phase_paired_audio_ready',runtime_changed=False,heard=False)
        save(a.out/'report.json',report)
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise
    print(report['result'])


if __name__=='__main__': main()
