"""Paired C-boundary timing and full native-stem preservation checks."""
import argparse,hashlib,json,time
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from vehicle_controller.native import Bridge,Engine

RATE=48000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def control(b,selection):
    c=deepcopy(b.initial(selection)[0]);c.update(mode=0,ignition=1,start_id=1,rpm=850.,load=0.,gain=.25)
    if selection==0:
        preset=Path('E:/VehicleSoundLab/references/analysis/startup_enable_v1/verification1/V10-startup-enabled.vslpreset.json')
        c=deepcopy(json.loads(preset.read_text())['control']);c.update(mode=0,ignition=1,start_id=1,rpm=850.,load=0.,gain=.25)
    return c

def run(b,selection,kind,seconds=8.,capture=True,chunk=240):
    total=round(seconds*RATE);c=control(b,selection);mix=[];stems=[];timing=[];cpu=[];telemetry=[]
    with Engine(b,selection) as e:
        while e.frame<total:
            frame=e.frame;t=(frame//240*240)/RATE;u=deepcopy(c)
            if kind=='sweep':
                u['rpm']=float(np.interp(t,[0,1.5,4.,5.5,7.,8.],[850,850,6500,6500,850,850]));u['load']=.7
                if 4.8<=t<5.4:u['dna'].update(line=.85,air=1.1,motion=.75)
            elif kind=='drive':
                u.update(mode=1,gear=1,automatic=1,throttle=float(np.interp(t,[0,1.3,1.5,4.5,4.8,6.],[0,0,1,1,0,0])),brake=.7 if t>=6 else 0.)
            elif kind=='catalog':u.update(rpm=4000.,load=.65)
            if kind!='catalog' and t>=seconds-.5:u['ignition']=0
            e.set(u);n=min(chunk,total-frame,240-frame%240)
            t0=time.perf_counter_ns();c0=time.thread_time_ns()
            ok=b.process(e.handle,e.mix,e.stems,n)
            cpu.append(time.thread_time_ns()-c0);timing.append(time.perf_counter_ns()-t0)
            if not ok:raise RuntimeError('C processing failed')
            e.frame+=n
            if capture:
                mix.append(np.ctypeslib.as_array(e.mix)[:n*2].copy().reshape(-1,2))
                stems.append(np.ctypeslib.as_array(e.stems)[:n*b.channels()].copy().reshape(n,-1))
                if frame%4800<240:telemetry.append(e.state())
    result=dict(process_seconds=sum(timing)*1e-9,thread_cpu_seconds=sum(cpu)*1e-9,
        block_p50_ms=float(np.percentile(timing,50))*1e-6,block_p99_ms=float(np.percentile(timing,99))*1e-6,
        block_max_ms=max(timing)*1e-6,frames=total,blocks=len(timing))
    return (np.concatenate(mix) if capture else None,np.concatenate(stems) if capture else None,result,telemetry)

def diff(a,b):
    d=a.astype(float)-b.astype(float);rms=float(np.sqrt(np.mean(d*d)));peak=float(np.max(abs(d)))
    ref=float(np.sqrt(np.mean(a.astype(float)**2)))
    return dict(exact=bool(np.array_equal(a,b)),max_error=peak,error_rms=rms,error_relative_db=20*np.log10(max(rms,1e-30)/max(ref,1e-30)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--repeats',type=int,default=3);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    old=Bridge(repo,a.old);new=Bridge(repo,a.new) if a.new else None
    cases=[(0,'idle',8.),(0,'sweep',8.),(0,'drive',8.)]+[(k,'catalog',2.5) for k in range(len(old.catalog))]
    report=dict(schema='vsl.source-performance/1',old_sha256=sha(a.old),new_sha256=sha(a.new) if a.new else None,cases={},timing={},claim='PC C-boundary processing only, not target MCPS or a hard real-time bound')
    for selection,kind,seconds in cases:
        name=f'{selection}-{kind}';print('Audio '+name,flush=True)
        x,s,t,state=run(old,selection,kind,seconds);np.savez(a.output/(name+'-before.npz'),mix=x,stems=s)
        row=dict(before=t)
        if selection==0 and kind in ('idle','sweep','drive'):sf.write(a.output/(name+'-before.wav'),x,RATE,subtype='FLOAT')
        if new:
            y,z,nt,ns=run(new,selection,kind,seconds);row.update(after=nt,mix=diff(x,y),stems=diff(s,z))
            assert row['mix']['max_error']<2e-6 and row['stems']['max_error']<2e-6,row
            for before,after in zip(state,ns):
                for key in before:
                    if key!='idle_weight':assert before[key]==after[key],(key,before[key],after[key])
            # Same adopted controls with arbitrary API partitioning; output and
            # all native stems must be exactly repeatable within the new code.
            if selection==0:
                y2,z2,_,_=run(new,selection,kind,seconds,chunk=217)
                assert np.array_equal(y,y2) and np.array_equal(z,z2)
                sf.write(a.output/(name+'-after.wav'),y,RATE,subtype='FLOAT')
            np.savez(a.output/(name+'-after.npz'),mix=y,stems=z)
        report['cases'][name]=row
    if new:
        for kind in ('idle','sweep','drive'):
            rows=[]
            for i in range(a.repeats):
                order=[('before',old),('after',new)] if i%2==0 else [('after',new),('before',old)]
                row={}
                for label,b in order:row[label]=run(b,0,kind,8.,capture=False)[2]
                rows.append(row);print('Timing '+kind+' '+str(i+1),flush=True)
            before=np.median([r['before']['process_seconds'] for r in rows]);after=np.median([r['after']['process_seconds'] for r in rows])
            cb=np.median([r['before']['thread_cpu_seconds'] for r in rows]);ca=np.median([r['after']['thread_cpu_seconds'] for r in rows])
            report['timing'][kind]=dict(runs=rows,median_before_seconds=float(before),median_after_seconds=float(after),
                median_process_reduction_percent=float(100*(1-after/before)),median_thread_cpu_reduction_percent=float(100*(1-ca/cb)))
    save(a.output/'report.json',report);print(json.dumps(dict(status='pass',timing=report['timing']),ensure_ascii=True),flush=True)
if __name__=='__main__':main()
