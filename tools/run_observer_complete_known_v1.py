"""Known-first complete-frame identities, node adjoints and dense fits."""
import argparse,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    from scipy import linalg
    from observer_complete_v1.frame import CompleteHann
    from observer_complete_v1.synthesis import WaveSynthesis
    from observer_complete_v1.fit import CompleteSystem,infer
    from observer_inverse_v1.fit import real_vector,complex_array
    repo=Path(__file__).resolve().parents[1];a.out.mkdir(parents=True,exist_ok=False)
    names=('research/observer_complete_v1_plan.json','tools/run_observer_complete_known_v1.py',
        'tools/observer_complete_v1/frame.py','tools/observer_complete_v1/synthesis.py','tools/observer_complete_v1/fit.py',
        'tools/observer_forward_v1/operator.py','tools/observer_forward_v1/polyphase.py',
        'tools/observer_inverse_v1/fit.py','tools/observer_inverse_v1/regularizer.py','tools/observer_inverse_v1/refinement.py')
    r=dict(result='running',frames=[],synthesis=[],solves=[],sources={},material_read=False)
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(dest)
    try:
        rng=np.random.default_rng(739421);N=4353;n=np.arange(N)
        first=np.zeros((N,2));first[0]=[1.,-.3]
        last=np.zeros((N,2));last[-1]=[.7,.2]
        pair=np.column_stack((np.cos(2*np.pi*7*n/1024)+.3*np.cos(2*np.pi*8*n/1024+.4),.4*np.cos(2*np.pi*7*n/1024+.7)))
        high=np.column_stack((np.cos(2*np.pi*287.37*n/1024)*(1+.2*np.sin(n*.013)),.5*np.cos(2*np.pi*286.61*n/1024+.8)))
        silent=pair.copy();silent[:,1]=0
        fixtures=(('first_impulse',first),('last_impulse',last),('neighbor_carriers',pair),
            ('between_harmonics_HF',high),('silent_right',silent),('arbitrary',rng.normal(size=(N,2))),('zero',np.zeros((N,2))))
        for name,audio in fixtures:
            op=CompleteHann(N);z=op.forward(audio);back=op.adjoint(z)
            reconstruction=float(abs(back-audio).max());energy=float(abs(np.vdot(z,z).real-np.vdot(audio,audio).real)/max(np.vdot(audio,audio).real,1.))
            test=rng.normal(size=z.shape)+1j*rng.normal(size=z.shape)
            gradient=op.adjoint(test)
            adjoint=float(abs(np.vdot(z,test).real-np.vdot(audio,gradient).real)/max(1,abs(np.vdot(z,test).real)))
            assert max(reconstruction,energy,adjoint)<2e-12
            path=a.out/('frame_'+name+'.npz')
            np.savez_compressed(path,audio=audio,rows=z,test_rows=test,gradient=gradient,coverage=op.coverage,starts=op.starts)
            r['frames'].append(dict(name=name,file=path.name,sha256=sha(path),reconstruction_error=reconstruction,relative_energy_error=energy,relative_adjoint_error=adjoint))
        N=4353;positions=np.rint(np.linspace(0,N-1,18)).astype(int);orders=np.array([3,7,10]);scale=np.array([[1.],[.3],[.05]])
        synthesis=WaveSynthesis(N,positions,orders);system=CompleteSystem(synthesis,scale,.7)
        columns=[]
        for j in range(system.nsize):
            x=np.zeros(system.nsize);x[j]=1;columns.append(system@x)
        matrix=np.array(columns).T
        np.savez_compressed(a.out/'dense_system.npz',matrix=matrix,positions=positions,orders=orders,scale=scale,wave_scale=.7,frames=N)
        for name in ('constant','ramp','rotation'):
            nodes=rng.normal(size=synthesis.shape)+1j*rng.normal(size=synthesis.shape)
            if name=='constant':nodes[:]=nodes[0]
            elif name=='ramp':nodes*=np.linspace(.1,1,len(nodes))[:,None,None]
            else:nodes*=np.exp(1j*np.linspace(0,2,len(nodes)))[:,None,None]
            audio=synthesis.synthesize(nodes);test=rng.normal(size=audio.shape);gradient=synthesis.adjoint(test)
            adj=abs(np.vdot(audio,test).real-np.vdot(nodes,gradient).real)/max(1,abs(np.vdot(audio,test).real))
            assert adj<2e-12
            path=a.out/('synthesis_'+name+'.npz');np.savez_compressed(path,nodes=nodes,audio=audio,test_wave=test,gradient=gradient,positions=positions,orders=orders)
            r['synthesis'].append(dict(name=name,file=path.name,sha256=sha(path)))
            fitted,info,right=infer(synthesis,audio,scale,.7)
            x=real_vector(fitted/scale[None]);b=system.rhs(audio);truth=np.linalg.lstsq(matrix,b,rcond=None)[0]
            error=float(np.linalg.norm(x-truth)/max(np.linalg.norm(truth),1e-24));assert info['converged'] and error<2e-7,(name,info,error)
            P=np.column_stack([right.apply(v) for v in np.eye(system.nsize)])
            assert abs(np.sum((matrix@P)**2,axis=0)-1).max()<2e-9
            path=a.out/('solve_'+name+'.npz');np.savez_compressed(path,target=audio,nodes=fitted,solution=x,dense_solution=truth,rhs=b,right=P,time=right.time,real_scale=right.real_scale,imag_scale=right.imag_scale)
            r['solves'].append(dict(name=name,file=path.name,sha256=sha(path),relative_solution_error=error,**info))
            print('KNOWN complete solve',name,info['iterations'],error,flush=True)
        N=5120;positions=np.rint(np.linspace(0,N-1,21)).astype(int);orders=np.arange(1,289)
        s=WaveSynthesis(N,positions,orders);nodes=(rng.normal(size=s.shape)+1j*rng.normal(size=s.shape))*.001
        audio=s.synthesize(nodes);test=rng.normal(size=audio.shape);g=s.adjoint(test)
        err=abs(np.vdot(audio,test).real-np.vdot(nodes,g).real)/max(1,abs(np.vdot(audio,test).real));assert err<2e-12
        path=a.out/'synthesis_full288.npz';np.savez_compressed(path,nodes=nodes,audio=audio,test_wave=test,gradient=g,positions=positions,orders=orders)
        r['synthesis'].append(dict(name='full288',file=path.name,sha256=sha(path)))
        r.update(result='observer_complete_known_ready',frame_controls=7,synthesis_controls=4,dense_controls=3,dense_sha256=sha(a.out/'dense_system.npz'))
        save(a.out/'report.json',r);print(r['result'],flush=True)
    except BaseException as error:r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
