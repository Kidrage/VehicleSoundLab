"""Independent scalar inverses, Gauss integration and half-angle control."""
import argparse,math,os,shutil,sys
from pathlib import Path
from research_archive_v1 import load,save,sha


def inverse(u,row,lo,hi):
    for j in range(len(lo)):
        if u<row[j+1] or j==len(lo)-1:return lo[j]+(u-row[j])/(row[j+1]-row[j])*(hi[j]-lo[j])
    raise AssertionError()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','study','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py');r=dict(result='running')
    try:
        d=load(a.study/'report.json');repo=Path(__file__).resolve().parents[1]
        assert d['result']=='quantile_seam_known_ready' and not d['material_read']
        for name,digest in d['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        assert sha(a.study/'seam.npz')==d['file_sha256']
        with np.load(a.study/'seam.npz') as z:data={k:z[k] for k in z.files}
        c,lo,hi=(data[k] for k in ('cdf','low','high'));expected=[]
        for p0,u in zip(data['product'],data['uniform']):
            w=min(max(float(p0),0.),1.);expected.append((1-w)*inverse(u,c[0],lo,hi)+w*inverse(u,c[1],lo,hi))
        phase_error=float(abs(np.asarray(expected)-data['phase']).max());assert phase_error<2e-12
        x,g=np.polynomial.legendre.leggauss(32);edges=sorted(set(c.ravel()));old=[];new=[]
        for w in data['weights']:
            # CDF mixtures have their original PHASE cells; integrate there.
            value=0j
            mass=np.diff((1-w)*c[0]+w*c[1])
            for j,m in enumerate(mass):
                angles=(lo[j]+hi[j])/2+(hi[j]-lo[j])*x/2
                value+=m*sum(g*np.exp(1j*angles))/2
            old.append(value)
            pieces=[]
            for start,end in zip(edges[:-1],edges[1:]):
                u=(start+end)/2+(end-start)*x/2
                q=[(1-w)*inverse(t,c[0],lo,hi)+w*inverse(t,c[1],lo,hi) for t in u]
                pieces.append((end-start)*sum(g*np.exp(1j*np.asarray(q)))/2)
            new.append(sum(pieces))
        moment_error=float(max(abs(np.asarray(old)-data['conditional_moment']).max(),abs(np.asarray(new)-data['quantile_moment']).max()))
        assert moment_error<2e-12 and abs(new[16]-old[16])>1.9
        a0=data['carrier']+data['common'];delta=data['delta'];expected=np.array([[math.cos(t+d/2),math.cos(t-d/2)] for t,d in zip(a0,delta)])
        assert abs(expected-data['stereo']).max()<2e-12
        assert abs(data['gauge_compensated']-expected).max()<2e-12 and abs(data['held_common']-expected).max()>1.9
        assert sha(a.study/'endcap_control.npz')==d['endcap_control_sha256']
        with np.load(a.study/'endcap_control.npz') as cap:
            raw,canonical=cap['raw'],cap['canonical'];truth=raw.copy()
            for row in truth:row[0]=0.;row[-1]=1.
            assert np.array_equal(truth,canonical) and np.array_equal(raw[:,1:-1],canonical[:,1:-1])
            for w in (0.,1.):
                target=0j;observed=0j
                for start,end in zip(sorted(set(canonical.ravel()))[:-1],sorted(set(canonical.ravel()))[1:]):
                    u=(start+end)/2+(end-start)*x/2
                    q=[(1-w)*inverse(t,canonical[0],cap['low'],cap['high'])+w*inverse(t,canonical[1],cap['low'],cap['high']) for t in u]
                    observed+=(end-start)*sum(g*np.exp(1j*np.asarray(q)))/2
                row=canonical[int(w)]
                for j,mass in enumerate(np.diff(row)):
                    theta=(cap['low'][j]+cap['high'][j])/2+(cap['high'][j]-cap['low'][j])*x/2
                    target+=mass*sum(g*np.exp(1j*theta))/2
                assert abs(observed-target)<2e-12
        r.update(result='independent_quantile_seam_known_passed',queries=len(expected),scalar_phase_queries=len(data['phase']),
                 maximum_phase_error=phase_error,maximum_moment_error=moment_error,
                 seam_negative_case_verified=True,common_pi_gauge_required_verified=True,endcap_preparation_verified=True,
                 producer_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),material_read=False)
        save(a.out/'report.json',r);print(r,flush=True)
    except BaseException as e:r.update(result='failed',error=repr(e));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
