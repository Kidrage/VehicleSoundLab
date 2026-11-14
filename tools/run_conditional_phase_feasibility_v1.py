"""Known controls then all frozen-source conditional-phase feasibility LPs."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--stage', choices=['known', 'real'], required=True)
    p.add_argument('--known', type=Path)
    p.add_argument('--known-audit', type=Path)
    a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[name] = '2'
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy.special import ndtri
    from scipy.stats import qmc
    from conditional_phase_v1.transport import amplitude_grid, phase_cells, project, hats
    from conditional_phase_v1.decoder import prepare, decode
    from radial_copula_v1.latent import independent_draws
    from relative_phase_v1.coordinates import decode as old_decode
    a.out.mkdir(parents=True, exist_ok=False)
    report = dict(result='running', stage=a.stage, sources={}, inputs={}, cases=[])
    try:
        names = ['research/conditional_phase_feasibility_v1_plan.json',
                 'tools/run_conditional_phase_feasibility_v1.py',
                 'tools/conditional_phase_v1/transport.py', 'tools/conditional_phase_v1/decoder.py',
                 'tools/radial_copula_v1/latent.py', 'tools/radial_copula_v1/quantiles.py',
                 'tools/relative_phase_v1/coordinates.py']
        for name in names:
            path = a.out/'exact_sources'/name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo/name, path); report['sources'][name] = sha(path)
        plan = load(repo/names[0]); gate = plan['checks']['primal_dual_normalized']

        def consume(path):
            report['inputs'][str(path)] = sha(path); return path

        def solve(folder, product, row_mass, cells, target, knots):
            fit = project(product, row_mass, cells['moments'], cells['masses'], target,
                          plan['LP']['primal_feasibility_tolerance'])
            assert max(fit[k] for k in ['primal_row_error','primal_column_error',
                'dual_feasibility_error','stationarity_error','primal_dual_gap']) <= gate
            assert fit['coupling'].min() >= -gate and abs(fit['actual_error_Linf']-fit['tau']) <= gate
            joint, cdf = prepare(fit['coupling'], row_mass, cells['masses'], plan['positivity_probe'])
            probabilities = np.diff(cdf, axis=1)
            assert probabilities.min() > 0
            actual = np.sum(joint*product[:, None]*cells['moments'][None, :])
            independent = np.dot(product, row_mass)*np.dot(cells['masses'], cells['moments'])
            assert abs(actual-((1-plan['positivity_probe'])*fit['actual']+
                              plan['positivity_probe']*independent)) < 2e-12
            uniform_slope = float(np.max((cells['high']-cells['low'])[None, :]/probabilities))
            if len(knots) > 1:
                dc = np.diff(cdf, axis=0)/np.diff(knots)[:, None]
                minimum = np.minimum(probabilities[:-1], probabilities[1:])
                product_slope = float(np.max((cells['high']-cells['low'])[None, :]/minimum*
                    np.maximum(abs(dc[:, :-1]), abs(dc[:, 1:]))))
            else:
                product_slope = 0.
            probe_product = np.repeat(np.linspace(knots[0], knots[-1], 5), 5)
            probe_uniform = np.tile(np.array([.017,.271,.5,.729,.983]), 5)
            probe_phase = decode(probe_product, probe_uniform, knots, cdf, cells['low'], cells['high'])
            folder.mkdir(parents=True, exist_ok=False)
            path = folder/'transport.npz'
            np.savez_compressed(path, product=product, row_mass=row_mass, knots=knots,
                **{'phase_'+k:v for k,v in cells.items()}, target=target,
                coupling=fit['coupling'], tau=fit['tau'], equality_dual=fit['equality_dual'],
                inequality_dual=fit['inequality_dual'], lower_dual=fit['lower_dual'],
                cdf=cdf, probe_product=probe_product, probe_uniform=probe_uniform, probe_phase=probe_phase)
            fields = {k:v for k,v in fit.items() if isinstance(v, float)}
            fields.update(sha256=sha(path), optimum_cross=[fit['actual'].real, fit['actual'].imag],
                positive_cross=[actual.real, actual.imag], target_cross=[target.real,target.imag],
                positive_error=float(abs(actual-target)),
                independent_cross=[independent.real,independent.imag],
                inverse_uniform_slope_bound=uniform_slope,
                inverse_product_slope_bound=product_slope,
                conditional_probability_min=float(probabilities.min()))
            return fields

        if a.stage == 'known':
            product = np.array([.5,1.5]); mass = np.array([.5,.5])
            fixtures = [
                ('independent',product,np.array([1.,-1.]),0j,0.),
                ('positive_association',product,np.array([1.,-1.]),.5+0j,0.),
                ('negative_association',product,np.array([1.,-1.]),-.5+0j,0.),
                ('constant_product_infeasible',np.ones(1),np.array([1.,-1.]),.2+0j,.2),
                ('fixed_phase',product,np.array([1j]),1j,0.),
                ('complex_target_infeasible',product,np.array([1.,1j]),1.2+1.2j,.7),
                ('quarter_turn',product,np.array([1j,-1j]),.5j,0.)]
            for label, values, moment, target, expected in fixtures:
                # Atomic controls validate LPs, not the continuous phase decoder.
                cells = dict(moments=moment, masses=np.full(len(moment),1/len(moment)),
                             low=np.angle(moment), high=np.angle(moment))
                row = solve(a.out/label, values, np.full(len(values),1/len(values)), cells, target, values)
                assert abs(row['tau']-expected) < plan['checks']['known_2x2_optimum']
                report['cases'].append(dict(label=label, expected_tau=expected, **row))
            try:
                amplitude_grid(np.zeros(16), plan['hat_knots'])
            except ValueError:
                report['cases'].append(dict(label='silent_rejected', rejected=True))
            else:
                raise AssertionError('Silent product was accepted')
            grid = amplitude_grid(np.linspace(.2,2.5,101),4)
            weights = hats(np.linspace(.2,2.5,101)/grid['mean'],grid['knots'])
            assert abs(weights.sum(axis=1)-1).max() < 2e-12
            cells = phase_cells(np.array([-1.,-.2,.3,1.]))
            joint = grid['masses'][:,None]*cells['masses'][None,:]
            amount = min(joint[0,1],joint[1,2])*.5
            joint[0,1]-=amount; joint[1,2]-=amount; joint[0,2]+=amount; joint[1,1]+=amount
            _,cdf=prepare(joint,grid['masses'],cells['masses'],plan['positivity_probe'])
            x=np.r_[grid['knots'][1:-1], [.7,1.3]]
            u=np.full(len(x),.413)
            difference=abs(decode(x+1e-10,u,grid['knots'],cdf,cells['low'],cells['high'])-
                           decode(x-1e-10,u,grid['knots'],cdf,cells['low'],cells['high'])).max()
            assert difference < plan['checks']['continuity_difference_radians']
            np.savez_compressed(a.out/'continuous_control.npz',**grid,**{'phase_'+k:v for k,v in cells.items()},
                                coupling=joint,cdf=cdf,probe_product=x,probe_uniform=u,maximum_difference=difference)
            report['continuous_control_sha256']=sha(a.out/'continuous_control.npz')
            report['result']='conditional_phase_known_controls_ready'
        else:
            known=load(consume(a.known/'report.json')); audit=load(consume(a.known_audit/'report.json'))
            assert known['result']=='conditional_phase_known_controls_ready'
            assert audit['result']=='independent_conditional_phase_audit_passed'
            assert audit['producer_sha256']==sha(a.known/'report.json') and known['sources']==report['sources']
            parent=a.workspace/'baselines/relative_phase_v1'
            manifest=load(consume(parent/'manifest.json'))
            assert sha(parent/'manifest.json')==load(repo/'research/relative_phase_v1_summary.json')['manifest_sha256']
            entries={r['path']:r['sha256'] for r in manifest['files']}
            def frozen(name):
                path=consume(parent/name); assert sha(path)==entries[name]; return path
            prior=load(frozen('evidence/real1/report.json'))
            bands=load(repo/'research/relative_phase_v1_plan.json')['bands_Hz']
            consume(repo/'research/relative_phase_v1_plan.json')
            errors={key:[] for key in ['parent_pooled','LP_class','positive_probe']}
            for old in prior['cases']:
                label=old['label']; folder=a.out/label; folder.mkdir()
                model=np.load(frozen(f'evidence/real1/{label}/profile.npz'))
                training=np.load(frozen(f'evidence/real1/{label}/training.npz'))
                raw=training['source_rows'].reshape(-1,288,2,2); z=raw[...,0]+1j*raw[...,1]
                target=np.mean(z[...,0]*z[...,1].conj(),axis=0)
                products=[]; energy=[]; baseline=[]; uniform_hashes=[]
                for previous in old['QMC']:
                    seed=previous['seed']
                    uniform=qmc.Sobol(d=1164,scramble=True,seed=seed).random_base2(plan['QMC']['power'])
                    digest=hashlib.sha256(uniform.tobytes()).hexdigest(); assert digest==previous['uniform_bytes_sha256']
                    amp,phase=old_decode(model,independent_draws(model,ndtri(uniform)))
                    products.append(amp[...,0]*amp[...,1]); energy.append(np.mean(amp**2,axis=0))
                    baseline.append(np.mean(products[-1]*np.exp(1j*(phase[...,0]-phase[...,1])),axis=0))
                    old_stats=np.load(frozen(f'evidence/real1/{label}/QMC_{seed}.npz'))
                    assert abs(products[-1].mean(axis=0)/old_stats['budget_amplitude_product']-1).max()<2e-12
                    uniform_hashes.append(dict(seed=seed,sha256=digest))
                product=np.concatenate(products); energy=np.mean(energy,axis=0); baseline=np.mean(baseline,axis=0)
                np.savez_compressed(folder/'inputs.npz',product=product,energy=energy,target=target,
                                    baseline=baseline,source_energy=np.mean(abs(z)**2,axis=0))
                row=dict(label=label,root_hz=old['root_hz'],input_sha256=sha(folder/'inputs.npz'),
                         original_QMC_uniform_hashes=uniform_hashes,harmonics=[])
                optimum=[]; positive=[]
                for h in range(288):
                    grid=amplitude_grid(product[:,h],plan['hat_knots'])
                    cells=phase_cells(model['phase'][:,288+h])
                    result=solve(folder/f'{h+1:03d}',grid['product'],grid['masses'],cells,target[h]/grid['mean'],grid['knots'])
                    result.update(order=h+1,mean_product=float(grid['mean']),
                        independent_phase_universal_gap=float(max(0,abs(target[h])/grid['mean']-1)))
                    optimum.append(grid['mean']*complex(*result['optimum_cross']))
                    positive.append(grid['mean']*complex(*result['positive_cross']))
                    row['harmonics'].append(result)
                row['bands']=[]; hz=np.arange(1,289)*old['root_hz']
                for lo,hi in bands:
                    mask=(hz>=lo)&(hz<hi)
                    ds=np.sqrt(np.mean(abs(z[:,mask,:])**2,axis=0).sum(axis=0).prod())
                    dm=np.sqrt(energy[mask].sum(axis=0).prod())
                    source=target[mask].sum()/ds
                    values=dict(parent_pooled=baseline[mask].sum()/dm,
                        LP_class=np.asarray(optimum)[mask].sum()/dm,positive_probe=np.asarray(positive)[mask].sum()/dm)
                    b=dict(band_Hz=[lo,hi],source=[source.real,source.imag])
                    for key,value in values.items():
                        b[key]=[value.real,value.imag]; errors[key].append(float(abs(value-source)))
                    row['bands'].append(b)
                report['cases'].append(row); save(a.out/'report.json',report)
                print('PASS all288 conditional phase LPs',label,flush=True)
            report['mean_band_complex_error']={k:float(np.mean(v)) for k,v in errors.items()}
            report['band_complex_errors']=errors
            report['class_inexact_harmonics']=sum(h['tau']>gate for r in report['cases'] for h in r['harmonics'])
            report['universal_finite_amplitude_gap_harmonics']=sum(h['independent_phase_universal_gap']>gate for r in report['cases'] for h in r['harmonics'])
            report['maximum_inverse_uniform_slope_bound']=max(h['inverse_uniform_slope_bound'] for r in report['cases'] for h in r['harmonics'])
            report['maximum_inverse_product_slope_bound']=max(h['inverse_product_slope_bound'] for r in report['cases'] for h in r['harmonics'])
            report['result']='six_source_conditional_phase_feasibility_ready'
        report['new_audio_or_runtime_adopted']=False
        save(a.out/'report.json',report); print(report['result'],flush=True)
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
