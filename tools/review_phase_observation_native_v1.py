"""Summarize qualified analytic observations; no vehicle fit or audio generation."""
import argparse
import csv
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','audit','latent','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    a.out.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    r=dict(result='running',sources={},inputs={},rows=[])
    try:
        for name in ('tools/review_phase_observation_native_v1.py','tools/audit_phase_observation_review_v1.py','tools/research_archive_v1.py'):
            dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
        source,proof,latent=load(a.study/'report.json'),load(a.audit/'report.json'),load(a.latent/'report.json')
        assert proof['verification_passed'] and proof['producer_sha256']==sha(a.study/'report.json')
        assert latent['verification_passed'] and latent['no_vehicle_profile_fit_or_audio_or_C_change']
        for path in (a.study/'report.json',a.audit/'report.json',a.latent/'report.json'):r['inputs'][str(path)]=sha(path)
        for case in source['cases']:
            path=a.study/(case['label']+'.npz');assert sha(path)==case['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:
                for observation in case['observations']:
                    v,c=observation['variant'],observation['cycles']
                    z=f[f'{v}_cycles{c}'][:,63];truth=f[f'truth_{v}_cycles{c}']
                    r['rows'].append(dict(case=case['label'],variant=v,cycles=c,rows=len(z),
                        observed_variation_RMS_FS=observation['observed']['variation_RMS_FS'],
                        truth_variation_RMS_FS=observation['truth']['variation_RMS_FS'],
                        envelope_RMSE_FS=float(np.sqrt(np.mean(np.sum(abs(z-truth)**2,axis=1)))),
                        native_query_coefficient_RMSE_FS=float(np.sqrt(np.mean(np.sum(abs(f[f'native_cycles{c}'][:,63]-f[f'query_cycles{c}'][:,63])**2,axis=1)))),
                        observed_lag8_skew_over_scale_squared=observation['observed']['lags'][-1]['skew_norm_over_source_scale_squared'],
                        truth_lag8_skew_over_scale_squared=observation['truth']['lags'][-1]['skew_norm_over_source_scale_squared'],
                        prefix40_variation_RMS_FS=observation['observed_prefix40']['variation_RMS_FS'],
                        hop1024_variation_RMS_FS=observation['hop1024_subset']['variation_RMS_FS']))
        fields=list(r['rows'][0])
        with (a.out/'observations.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(r['rows'])
        def row(case,variant,cycles):return next(v for v in r['rows'] if (v['case'],v['variant'],v['cycles'])==(case,variant,cycles))
        cases=('common_AM','relative_PM','sideband');windows=(2,4,8)
        fig,axes=plt.subplots(1,2,figsize=(12,4.8),constrained_layout=True)
        for case in cases:
            values=[row(case,'canonical',c) for c in windows]
            axes[0].plot(windows,[v['observed_variation_RMS_FS']/v['truth_variation_RMS_FS'] for v in values],'o-',label=case)
        axes[0].set(xlabel='Hann window (cycles)',ylabel='Observed / instantaneous envelope variation RMS',
            title='Known modulation is smoothed by the observer',xticks=windows,ylim=(0,1.05))
        axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
        clockcases=('static','static_matching_variable_clock','static_mismatched_clock')
        x=np.arange(3)
        for delta,variant in ((-.2,'canonical'),(0.,'query'),(.2,'native')):
            axes[1].bar(x+delta,[max(row(c,variant,4)['observed_variation_RMS_FS'],1e-17) for c in clockcases],width=.2,label=variant)
        axes[1].set_yscale('log');axes[1].set_xticks(x,('Fixed matched','Variable matched','0.02% clock mismatch'))
        axes[1].tick_params(axis='x',labelsize=8)
        axes[1].set(ylabel='Envelope variation RMS (FS; stereo Euclidean norm)',title='Same static source; observer coordinates matter')
        axes[1].legend(fontsize=8);axes[1].grid(alpha=.2,axis='y')
        fig.suptitle('Analytic controls, carrier64 | not vehicle fidelity or an electronic-timbre diagnosis')
        for ext in ('png','svg'):fig.savefig(a.out/('observation_controls.'+ext),dpi=150)
        plt.close(fig)
        r.update(result='native_observation_review_published',known_cases=9,
            latent_report=dict(result=latent['result'],maximum_error=latent['maximum_error'],
                scalar_interpolation_error=latent['independent_scalar_interpolation_error_on_coupled_law']),
            no_vehicle_fit_training_audio_C_or_causal_hearing_claim=True,new_C1_source_eligible_for_statistics=False,
            files={p.name:sha(p) for p in sorted(a.out.iterdir()) if p.is_file()})
        save(a.out/'report.json',r);print(r['result'],len(r['rows']),flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
