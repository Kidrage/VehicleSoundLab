"""Direct event sums and numerical Fourier integrals, then immutable snapshot."""
import json
import shutil
from runtime_review import ROOT,sha
import numpy as np
import soundfile as sf
from scipy.integrate import quad

OUT=ROOT/'renders/pressure_sampling_v1'
SNAP=ROOT/'baselines/pressure_sampling_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def event_sum(meta,indices):
    t=meta['warmup_seconds']+indices/meta['sample_rate'];cycle=meta['cycle_hz']
    values=np.zeros((len(indices),2))
    for event in meta['events']:
        times=(event['cycle_fraction']+np.arange(int(t[-1]*cycle)+1))/cycle
        ages=t[:,None]-times[None,:];exists=ages>=-1e-12;ages=np.maximum(ages,0)
        for mode in meta['modes']:
            if mode['enabled']:
                h=np.exp(-ages/mode['decay_seconds'])*np.sin(2*np.pi*mode['hz']*ages)*exists
                values[:,event['bank']]+=meta['pressure_level']*event['strength']*mode['weight']*h.sum(axis=1)
    return values


def quadrature_checks(meta,ideal):
    def impulse(t):
        return sum(m['weight']*np.exp(-t/m['decay_seconds'])*np.sin(2*np.pi*m['hz']*t)
            for m in meta['modes'] if m['enabled'])
    n=len(ideal);cycle=meta['cycle_hz'];cycles=round(n/meta['sample_rate']*cycle)
    spectrum=np.fft.fft(ideal,axis=0)/n;checks=[]
    stop=40*max(m['decay_seconds'] for m in meta['modes'] if m['enabled'])
    tail_bound=sum(abs(m['weight'])*m['decay_seconds']*np.exp(-stop/m['decay_seconds'])
        for m in meta['modes'] if m['enabled'])
    for target in [0,1050,2900,6100,7999]:
        order=round(target/cycle);frequency=order*cycle
        real,real_error=quad(lambda t:impulse(t)*np.cos(2*np.pi*frequency*t),0,stop,epsabs=1e-12,epsrel=1e-10,limit=2000)
        imag,imag_error=quad(lambda t:impulse(t)*np.sin(2*np.pi*frequency*t),0,stop,epsabs=1e-12,epsrel=1e-10,limit=2000)
        coefficient=np.zeros(2,complex)
        for event in meta['events']:
            coefficient[event['bank']]+=meta['pressure_level']*cycle*event['strength']*np.exp(-2j*np.pi*order*event['cycle_fraction'])*(real-1j*imag)
        actual=spectrum[order*cycles]
        error=float(abs(coefficient-actual).max());assert error<2e-10,(target,error)
        checks.append(dict(frequency_hz=frequency,maximum_complex_coefficient_error=error,
            finite_integration_stop_seconds=stop,analytic_omitted_impulse_integral_tail_bound=tail_bound,
            quadrature_reported_error_estimate=float(max(real_error,imag_error))))
    return checks


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():raise SystemExit('Preserve pressure_sampling_v1.')
    result=read(OUT/'results.json')
    for group in ['sources','inputs','files']:
        for name,digest in result[group].items():assert sha((OUT if group=='files' else ROOT)/name)==digest,name
    direct={};integrals={}
    for name,row in result['runs'].items():
        x,sr=sf.read(OUT/(name+'.wav'),always_2d=True);ideal,ideal_sr=sf.read(OUT/(name+'_ideal.wav'),always_2d=True)
        meta=row['meta'];assert sr==ideal_sr==meta['sample_rate'] and x.shape==ideal.shape
        indices=np.unique(np.linspace(0,len(x)-1,257,dtype=int))
        oracle=event_sum(meta,indices);error=float(abs(x[indices]-oracle).max());assert error<2e-9,(name,error)
        d=x-ideal;error_power=np.var(d,axis=0);ideal_power=np.var(ideal,axis=0)
        ratio=10*np.log10(error_power/ideal_power)
        expected=row['score']['bands']['AC']['error_over_ideal_db_lr']
        # The analytical report used double ideal samples; the saved ideal WAV
        # is float32. Bound that serialization error instead of ignoring it.
        epsilon=np.max(np.spacing(np.abs(ideal).astype(np.float32)),axis=0)/2
        error_norm=np.sqrt(error_power);ideal_norm=np.sqrt(ideal_power)
        lower=20*np.log10(np.maximum(error_norm-epsilon,1e-30)/(ideal_norm+epsilon))
        upper=20*np.log10((error_norm+epsilon)/np.maximum(ideal_norm-epsilon,1e-30))
        assert np.all(np.asarray(expected)>=lower-1e-10) and np.all(np.asarray(expected)<=upper+1e-10)
        direct[name]=dict(direct_finite_event_sum_error=error,independent_serialized_time_domain_AC_ratio_db_lr=ratio.tolist(),
            maximum_ideal_float32_sample_rounding_bound_lr=epsilon.tolist(),
            double_report_ratio_rounding_interval_db_lr=np.column_stack([lower,upper]).tolist())
        if sr==48000:integrals[name]=quadrature_checks(meta,ideal)
    manifest_path=ROOT/'baselines/v0.17.0/manifest.json';native=read(manifest_path);preserved={}
    for item in native['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','AGENTS.md','build.ps1','Launch.cmd','Launch-character.cmd','Launch-current.cmd']:
            assert sha(ROOT/name)==item['sha256'],name;preserved[name]=item['sha256']
    binaries=read(ROOT/'renders/v0.17.0/verification.json')['binaries']
    for name,digest in binaries.items():assert sha(ROOT/'build-v017/Release'/name)==digest,name
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==29
    names=set(result['sources'])|set(result['inputs'])|{
        'tools/verify_pressure_sampling.py','tools/runtime_review.py','research/压力层采样核查V1.md',
        'research/goal_progress_pressure_sampling_v1.json','README.md'}
    verification=dict(result='pass',study='pressure_sampling_v1',independent_finite_event_sums=direct,
        numerical_impulse_Fourier_integrals=integrals,native_source_contracts_unchanged=preserved,
        native_binaries_unchanged=binaries,previous_snapshot_manifest_identities=history,
        sources_and_dependencies={name:sha(ROOT/name) for name in sorted(names)},
        artifacts={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
        scope='Unmodulated native pressure-module sampling diagnosis,not actual full-mix alias power or subjective electronic-timbre cause. No runtime/voice change. Original references not processed. Previous manifest identities retained,not a new full-content audit.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False),encoding='utf-8')
    SNAP.mkdir()
    for name in sorted(names):
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            target=SNAP/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest=dict(study='pressure_sampling_v1',base_runtime='0.17.0 unchanged',files=files,
        status='Frozen controlled pressure sampling diagnosis. Quantifies ideal-bandlimited difference; no native fix or subjective acceptance implied.',
        storage='Probe/analysis/verification sources,linked native library and source manifest,all15 raw and ideal float pairs,metadata and evidence retained. Actual native include dependency stays in baselines/v0.17.0.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    complete=dict(result='pass',snapshot_files=len(files),manifest_sha256=sha(SNAP/'manifest.json'),
        verification_sha256=sha(OUT/'verification.json'),native_contracts_unchanged=len(preserved),
        maximum_direct_event_sum_error=max(x['direct_finite_event_sum_error'] for x in direct.values()),
        maximum_quadrature_coefficient_error=max(x['maximum_complex_coefficient_error'] for rows in integrals.values() for x in rows))
    (OUT/'freeze_complete.json').write_text(json.dumps(complete,indent=2),encoding='utf-8');print(json.dumps(complete,indent=2))


if __name__=='__main__':main()
