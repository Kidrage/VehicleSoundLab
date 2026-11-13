"""Audit new idle transitions, continuous-source parity and frozen legacy audio."""
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--proof',type=Path,required=True)
p.add_argument('--level-proof',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(a.workspace/'tools'/x) for x in ('ipm_deps','qp_deps','python_deps')]
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',commands=[],legacy=[],generated=[],runtime_default_changed=False,timbre_accepted=False)
def run(label,argv):
    start=time.perf_counter();done=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=180)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    row=dict(label=label,argv=list(map(str,argv)),exit=done.returncode,seconds=time.perf_counter()-start,log_sha256=sha(path))
    r['commands'].append(row);save(a.out/'report.json',r);print(json.dumps(row),flush=True)
    assert done.returncode==0,(label,path)
try:
    proof=load(a.proof/'report.json');assert proof['result']=='passed' and proof['phase']=='all' and proof['tests']==57
    for name,digest in proof['sources'].items():assert sha(repo/name)==sha(a.proof/'exact_sources'/name)==digest,name
    level=load(a.level_proof/'report.json');assert level['result']=='one_fixed_monitoring_trim_derived'
    level_gain=level['level_gain'];assert sha(repo/'experiments/idle_state_v1/study.h')==level['generated_header_sha256']
    r.update(level_gain=level_gain,level_proof_sha256=sha(a.level_proof/'report.json'))
    r['build_proof_sha256']=sha(a.proof/'report.json');r['source_sha256']=sha(Path(__file__))
    shutil.copy2(__file__,a.out/'executed_render.py')
    bin_dir=repo/'build-idle-state-v1/bin/Release';(a.out/'bin').mkdir()
    for name in ['idle_state_probe.exe','VslAtlasDrive_probe.exe']:
        shutil.copy2(bin_dir/name,a.out/'bin'/name)
    r['binaries']={x.name:sha(x) for x in (a.out/'bin').iterdir()}
    for name in ['F2_fixed_idle.msource','F2_fixed_idle.rdetail']:
        current=repo/'experiments/modal_idle_v1'/name
        assert sha(current)==sha(a.workspace/'baselines/idle_modal_c_v1/source/experiments/modal_idle_v1'/name)
    prior=a.workspace/'references/analysis/idle_modal_v1/trial4'
    traces={};stems={};frames=384000;seed=149921
    for enabled in [0,1]:
        folder=a.out/('enabled' if enabled else 'disabled');folder.mkdir();prefix=folder/'C'
        run('render_'+str(enabled),[a.out/'bin/idle_state_probe.exe',prefix,enabled,seed])
        trace=np.fromfile(folder/'C_trace.f64',dtype='<f8').reshape((-1,6));assert trace.shape==(frames,6)
        names=['mix','modal_raw','detail_raw','idle_raw','idle_added','retained_old']
        audio={}
        for name in names:
            x,rate=sf.read(folder/f'C_{name}.wav',always_2d=True);assert rate==48000 and x.shape==(frames,2) and np.isfinite(x).all()
            audio[name]=x
        comparisons=[]
        for name,parent in [('modal_raw','modal_only.wav'),('detail_raw',f'detail_{seed}.wav'),('idle_raw',f'mix_{seed}.wav')]:
            expected,rate=sf.read(prior/parent,always_2d=True);error=float(abs(audio[name]-expected[:frames]).max())
            assert rate==48000 and error<=1e-7,(enabled,name,error)
            comparisons.append(dict(stem=name,maximum_FS_error=error,frozen_parent_sha256=sha(prior/parent)))
        life,op=trace[:,1],trace[:,2]
        gate=((life==4)&(op==0)) if enabled else np.zeros(frames,dtype=bool)
        # Reconstruct each ramp by its endpoints and integer time, not the C
        # per-sample additive ramp. Keep the original3840sample contract.
        position=np.zeros(frames);previous_gate=False;start=0.;target=0.;first=0
        for n,value in enumerate(gate):
            if bool(value)!=previous_gate:
                start=position[n-1] if n else 0.;target=float(value);first=n;previous_gate=bool(value)
            u=min(1.,(n-first+1)/3840) if target!=start else 1.
            position[n]=start+(target-start)*u
        expected_weight=position*position*(3-2*position)
        ramp_error=float(abs(trace[:,4]-expected_weight).max());assert ramp_error<1e-10
        assert np.array_equal(trace[:,5],1-trace[:,4])
        expected_added=audio['idle_raw']*(trace[:,3]*trace[:,4]*level_gain)[:,None]
        added_error=float(abs(expected_added-audio['idle_added']).max());assert added_error<1e-7
        accounting=float(abs(.25*(audio['retained_old']+audio['idle_added'])-audio['mix']).max());assert accounting<1e-7
        assert np.all((life>=0)&(life<=5)&(op>=0)&(op<8))
        transitions=np.r_[0,np.flatnonzero((np.diff(life)!=0)|(np.diff(op)!=0))+1]
        peak=float(abs(audio['mix']).max());assert peak<1
        r['generated'].append(dict(enabled=enabled,seed=seed,frames=frames,peak=peak,
            raw_parity=comparisons,ramp_maximum_error=ramp_error,added_maximum_FS_error=added_error,
            float_stem_accounting_maximum_FS_error=accounting,gate_samples=int(gate.sum()),
            state_entries=[dict(frame=int(i),seconds=float(i/48000),lifecycle=int(life[i]),operating=int(op[i]),rpm=float(trace[i,0])) for i in transitions],
            file_sha256={x.name:sha(x) for x in folder.iterdir() if x.is_file()}))
        traces[enabled]=trace;stems[enabled]=audio
    assert np.array_equal(traces[0][:,:4],traces[1][:,:4])
    for name in ['modal_raw','detail_raw','idle_raw']:assert np.array_equal(stems[0][name],stems[1][name])
    r['entire_controller_and_envelope_trace_exact']=True
    old=a.workspace/'references/analysis/drive_resonance_v1/before1';snapshot=load(old/'snapshot.json')
    folder=a.out/'legacy';folder.mkdir()
    for case in snapshot['cases']:
        options=case['options']+(['--stereo-bed','1'] if case['name'].startswith('E_') else [])
        run(case['name'],[a.out/'bin/VslAtlasDrive_probe.exe',*case['models'][:2],folder/case['name'],*options])
        original=sorted((old/'renders').glob(case['name']+'_*.wav'));assert len(original)==28
        for path in original:
            assert sha(path)==snapshot['files'][path.relative_to(old).as_posix()]
            assert path.read_bytes()==(folder/path.name).read_bytes(),path.name
        trace=case['name']+'_trace.csv';assert (old/'renders'/trace).read_bytes()==(folder/trace).read_bytes()
        r['legacy'].append(dict(case=case['name'],WAV_bytes_exact=28,controller_trace_exact=True))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure,axes=plt.subplots(3,1,figsize=(11,7),sharex=True,layout='constrained')
    trace=traces[1];times=np.arange(frames)/48000
    axes[0].plot(times[::240],trace[::240,0]);axes[0].set(ylabel='Engineering RPM',title='One existing driver; F2 candidate stays at modal ratio1 (not calibrated to RPM)')
    axes[1].plot(times[::24],trace[::24,4],label='Candidate weight');axes[1].plot(times[::24],trace[::24,5],label='Old source retention');axes[1].legend();axes[1].set(ylabel='Complementary weight',ylim=(-.05,1.05))
    for enabled,label in [(0,'Original path'),(1,'Opt-in idle candidate')]:
        blocks=stems[enabled]['mix'].reshape((-1,960,2));power=np.sqrt(np.mean(blocks*blocks,axis=(1,2)))
        axes[2].plot((np.arange(len(power))+.5)*.02,power,label=label)
    axes[2].set(xlabel='Time (s)',ylabel='20ms stereo RMS (FS)');axes[2].legend()
    figure.savefig(a.out/'idle_state_trace.png',dpi=150);plt.close(figure)
    r.update(result='continuous_idle_state_and_all84_legacy_WAVs_verified',CTest_count=57,
        output_only_stereo=True,physical_7_1_4_verified=False,actual_F2_RPM_calibrated=False,
        native_UI_or_default_changed=False,schema8_supports_processor=False,
        limitation='Different F2 LP610 and A Performante contexts; this is a source/state plumbing study, not accepted same-car idle-to-acceleration timbre')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
