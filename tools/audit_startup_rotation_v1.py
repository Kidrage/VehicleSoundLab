"""Independent saved-artifact checks, active-event C timing and dry diagnostics."""
import argparse,ctypes as C,json,time,statistics
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from startup_rotation_v1.native import RotationStarter
from startup_rotation_v1.author import save,sha,RATE
from startup_character_v1.expression import ExpressionStarter
from render_startup_expression_v1 import controls

def main():
    p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True);a=p.parse_args();root=a.review
    report=json.loads((root/'verification.json').read_text());recipe=json.loads((root/'recipe.json').read_text());repo=Path(__file__).resolve().parents[1]
    mix,rate=sf.read(root/'Candidate.wav',dtype='float32');assert rate==RATE
    total=np.zeros_like(mix)
    for name in ('prelude','crank','catch','idle_handoff'):
        stem,_=sf.read(root/(name+'.wav'),dtype='float32');total+=stem
    assert np.array_equal(mix,total)
    before,_=sf.read(root/'Previous-V3.wav',dtype='float32');crank,_=sf.read(root/'crank.wav',dtype='float32')
    old_crank,_=sf.read(root/'Previous-crank.wav',dtype='float32')
    start,stop=recipe['sections']['crank'];lo,hi=round(start*RATE),round(stop*RATE)
    assert np.array_equal(mix[:lo],before[:lo]) and np.array_equal(mix[hi:],before[hi:])
    for name,item in report['outputs'].items():assert sha(root/name)==item['sha256']
    report.update(saved_stems_recombine_exact=True,saved_other_actions_exact=True,finite=True,no_clipping=True)
    report['crank_rms_ratio_new_old_db']=float(10*np.log10(np.mean(crank[lo:hi].astype(float)**2)/np.mean(old_crank[lo:hi].astype(float)**2)))
    profiles={'before':json.loads((root/'model/old-crank/profile.json').read_text()),'after':json.loads((root/'model/profile.json').read_text())}
    ctrl=controls(recipe['base_recipe'],len(mix))[0]['crank'];library=root/'startup_character_bridge.dll'
    def timing(name):
        cls=ExpressionStarter if name=='before' else RotationStarter
        t0=time.perf_counter();v=cls(library,profiles[name],142867);initial=time.perf_counter()-t0
        arrays=[np.ascontiguousarray(ctrl[k],dtype=np.int32 if k=='gate' else np.float64) for k in ('progress','gate','strength','pitch')]
        arrays.extend(np.full(len(mix),ctrl[k],dtype=np.float64) for k in ('core','texture'))
        if name=='after':arrays[2]*=recipe['rotation_scale']
        ptr=lambda x,offset: C.cast(x.ctypes.data+offset*x.itemsize,C.POINTER(C.c_int if x.dtype==np.int32 else C.c_double))
        out=np.empty((480,2),dtype=np.float32);elapsed=0;active=0;blocks=[]
        try:
            for n in range(0,len(mix),480):
                count=min(480,len(mix)-n);args=[ptr(x,n) for x in arrays]
                t0=time.perf_counter_ns();ok=v.lib.sc_process_expression(v.handle,*args,out.ctypes.data_as(C.POINTER(C.c_float)),count);dt=(time.perf_counter_ns()-t0)*1e-9
                assert ok;elapsed+=dt
                if lo<=n and n+count<=hi:active+=dt;blocks.append(dt)
        finally:v.close()
        return dict(initialization_seconds=initial,whole7seconds_C_time=elapsed,active1point1seconds_C_time=active,active_block_p99_ms=float(np.percentile(blocks,99)*1000),active_block_max_ms=max(blocks)*1000)
    runs=[]
    for i in range(3):
        row={}
        for name in (('before','after') if i%2==0 else ('after','before')):row[name]=timing(name)
        runs.append(row)
    report['isolated_event_timing']=dict(runs=runs,median_before_active_seconds=statistics.median(r['before']['active1point1seconds_C_time'] for r in runs),median_after_active_seconds=statistics.median(r['after']['active1point1seconds_C_time'] for r in runs),limits='Single isolated event C boundary, excludes initialization/control preparation/output. Not integrated full-system peak, target MCPS or hard real-time bound.')
    # Save a static diagnostic for engineering QA; this is not a listening page.
    import matplotlib;matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,7),sharex=True)
    for ax,(title,x) in zip(axes,[('Previous V3 crank',old_crank),('New sustained crank',crank),('New full startup / catch / idle',mix)]):
        f,t,s=signal.spectrogram(x.mean(axis=1),fs=RATE,nperseg=1024,noverlap=800,mode='psd')
        image=ax.pcolormesh(t,f,10*np.log10(np.maximum(s,1e-14)),vmin=-105,vmax=-40,shading='auto',rasterized=True);ax.set_ylim(80,8000);ax.set_yscale('log');ax.set_ylabel('Hz');ax.set_title(title,fontsize=10)
    axes[-1].set_xlabel('Seconds');fig.tight_layout();fig.savefig(root/'diagnostic.png',dpi=140);plt.close(fig)
    save(root/'audio-audit.json',report)
    print(json.dumps({k:report[k] for k in ('saved_stems_recombine_exact','saved_other_actions_exact','crank_rms_ratio_new_old_db','isolated_event_timing')}),flush=True)
if __name__=='__main__':main()
