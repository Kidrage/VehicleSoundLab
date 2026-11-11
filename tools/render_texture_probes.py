"""Float32 measurement grid from the unchanged frozen V015 C synthesizer."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from runtime_review import ROOT,sha
import soundfile as sf

OUT=ROOT/'references/analysis/texture_v1'
PROBE=ROOT/'build-research-texture/Release/texture_probe.exe'


def main():
    if (OUT/'probes.json').exists():raise SystemExit('Preserve completed probes.')
    (OUT/'runtime').mkdir(parents=True,exist_ok=True)
    before={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [PROBE,ROOT/'build-v015/Release/vsl_core.lib']}
    def render_case(rpm,load,pure):
        name=f'rpm{rpm}_load{round(load*100)}_'+('osc' if pure else 'full')
        prefix=OUT/'runtime'/name;compat=int(rpm in [1200,8000] and load==.85)
        args=[str(PROBE),str(prefix),str(rpm),str(load),str(pure),str(compat)]
        done=subprocess.run(args,check=True,capture_output=True,text=True,timeout=60)
        assert 'DSP 0.15.0' in done.stdout
        info=sf.info(prefix.with_suffix('.wav'));assert info.subtype=='FLOAT' and info.frames==288000 and info.channels==2
        check=None
        if compat:
            frozen=prefix.with_name(name+'_frozen.wav');options=['--rpm',str(rpm),'--load',str(load),'--seconds','6']
            if pure:options.append('--pure')
            subprocess.run([str(ROOT/'baselines/v0.15.0/bin/vsl_render.exe'),str(frozen),*options],check=True,capture_output=True,timeout=60)
            assert frozen.read_bytes()==prefix.with_name(name+'_compat.wav').read_bytes()
            check=sha(frozen)
        return name,dict(rpm=rpm,load=load,pure_osc=bool(pure),command=args,stdout=done.stdout,
            seconds=6,measurement_interval_seconds=[2.5,5.8],frozen_compatibility_pcm_sha256=check)
    rows={}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(render_case,r,l,p) for r in [1200,2400,4000,6000,8000] for l in [.18,.85] for p in [0,1]]
        for future in as_completed(jobs):
            name,row=future.result();rows[name]=row;print('rendered',name,flush=True)
    for path,digest in before.items():assert sha(ROOT/path)==digest
    result=dict(schema='vsl.frozen-texture-probes/1',dsp='0.15.0',seed=48271,
        probe_source_sha256=sha(ROOT/'tools/texture_probe/probe.c'),linked_inputs=before,
        definition='Default V10 bench engineering parameters; full and Pure OSC. Float32 before PCM16 device quantization, no added endpoint fade, normalization or reference audio.',
        not_established='None of these RPM/load cells is matched to reference vehicle telemetry.',cases=dict(sorted(rows.items())))
    result['files']={str(p.relative_to(OUT)).replace('\\','/'):sha(p) for p in sorted((OUT/'runtime').iterdir()) if p.is_file()}
    (OUT/'probes.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('20 float/source/take probes complete; four PCM renders byte-identical with frozen V015.',flush=True)


if __name__=='__main__':main()
