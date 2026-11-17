"""Independent native power/phase/width/correspondence checks; no observer imports."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load,save,sha


def finite_oracle(audio,frames,hop):
    starts=np.arange(0,len(audio)-frames+1,hop)
    win=np.hanning(frames+1)[:-1]
    data=audio[starts[:,None]+np.arange(frames)]*win[None,:,None]
    z=np.fft.rfft(data,axis=1)
    scale=np.full(frames//2+1,2/(frames*np.dot(win,win)))
    scale[0]*=.5;scale[-1]*=.5
    p=(z.real*z.real+z.imag*z.imag)*scale[None,:,None]
    weighted=np.sum(data*data,axis=1)/np.dot(win,win)
    np.testing.assert_allclose(p.sum(axis=1),weighted,atol=2e-14,rtol=2e-12)
    selected=np.array([0,3,17,frames//7,frames//2])
    # Literal finite DFT independently checks selected native coefficients.
    direct=np.exp(-2j*np.pi*selected[:,None]*np.arange(frames)/frames)@data[0]
    np.testing.assert_allclose(direct,z[0,selected],atol=2e-10,rtol=2e-10)
    center=z*((-1.)**np.arange(len(scale)))[None,:,None]*(2/win.sum())
    return p,center


def width_oracle(power,index,df):
    half=.5*power[index]
    before=np.flatnonzero(power[:index]<=half)
    after=np.flatnonzero(power[index+1:]<=half)
    if not len(before) or not len(after):return None
    left=int(before[-1]);right=int(index+1+after[0])
    if left==0 or right==len(power)-1:return None
    xleft=np.interp(half,power[left:left+2],[left,left+1])
    xright=np.interp(half,power[right-1:right+1][::-1],[right,right-1])
    return float((xright-xleft)*df)


def check_rows(document,power,center):
    df=document['frequency_bin_hz'];rows=document['inventories'];connections=document['links']
    largest=0.
    for row in rows:
        j=row['frame'];assert row['first_sample']==j*document['hop_frames']
        for peak in row['peaks']:
            k=peak['bin'];mean=power[j].mean(axis=-1)
            np.testing.assert_allclose(peak['power_LR'],power[j,k],atol=2e-14,rtol=2e-12)
            value=np.array(peak['coefficient_real_LR'])+1j*np.array(peak['coefficient_imag_LR'])
            error=float(abs(value-center[j,k]).max());largest=max(largest,error)
            assert error<2e-12
            expected=width_oracle(mean,k,df);actual=peak['half_power_width_hz']
            assert (expected is None)==(actual is None)
            if expected is not None:assert abs(expected-actual)<1e-9
    offset=0
    for left,right in zip(rows[:-1],rows[1:]):
        dt=right['centre_seconds']-left['centre_seconds']
        radius=1.5*df+1500*dt
        b=np.array([p['hz'] for p in right['peaks']])
        lists=[list(range(int(np.searchsorted(b,p['hz']-radius)),int(np.searchsorted(b,p['hz']+radius,side='right')))) for p in left['peaks']]
        incoming=np.bincount([j for indices in lists for j in indices],minlength=len(b))
        for i,indices in enumerate(lists):
            item=connections[offset];offset+=1
            assert item['left_frame']==left['frame'] and item['right_frame']==right['frame']==left['frame']+1
            assert item['left']==i and item['candidates']==indices
            unique=len(indices)==1 and incoming[indices[0]]==1
            expected='unique' if unique else ('ambiguous' if indices else 'absent')
            assert item['state']==expected
            if unique:
                j=indices[0];assert item['right']==j
                apeak,bpeak=left['peaks'][i],right['peaks'][j]
                za=center[left['frame'],apeak['bin']];zb=center[right['frame'],bpeak['bin']]
                phase=np.angle(zb*za.conjugate())/(2*np.pi)-.5*(apeak['hz']+bpeak['hz'])*dt
                phase=(phase+.5)%1-.5
                actual=np.array(item['phase_residual_cycles_LR'])
                # Compare modulo one cycle at the -0.5/+0.5 boundary.
                assert abs((phase-actual+.5)%1-.5).max()<2e-12
    assert offset==len(connections)
    return largest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,args.output/Path(__file__).name)
    report=dict(result='running',cases=[],goal_complete=False,timbre_accepted=False)
    save(args.output/'report.json',report)
    try:
        original=load(args.input/'report.json');assert original['result']=='passed'
        for case in original['cases']:
            folder=args.input/case['id']
            x,sr=sf.read(folder/'source.wav',always_2d=True);assert sr==48000
            assert sha(folder/'source.wav')==case['source_wave_sha256']
            binding=case['source'];assert sha(binding['path'])==binding['sha256']
            with sf.SoundFile(binding['path']) as stream:
                stream.seek(binding['first_frame']);raw=stream.read(len(x),always_2d=True)
            np.testing.assert_array_equal(x,raw)
            for item in case['observations']:
                path=folder/(item['id']+'.json');assert sha(path)==item['sha256']
                document=load(path)
                p,c=finite_oracle(x,document['window_frames'],document['hop_frames'])
                saved=np.load(folder/(item['id']+'.npz'))
                np.testing.assert_allclose(saved['power_LR'],p,atol=2e-14,rtol=2e-12)
                np.testing.assert_allclose(saved['complex_center_LR'],c,atol=2e-12,rtol=2e-12)
                error=check_rows(document,p,c)
                report['cases'].append(dict(source=case['id'],observation=item['id'],windows=len(p),
                    inventories_and_adjacent_graph_verified=True,maximum_complex_error_FS=error))
            save(args.output/'report.json',report)
        report.update(result='passed',observations=len(report['cases']),
            input_report_sha256=sha(args.input/'report.json'),physical_classifier_qualified=False)
    except Exception as error:
        report.update(result='failed',error=repr(error));save(args.output/'report.json',report)
        raise
    save(args.output/'report.json',report)
    print('native powers, centre phases, widths and all adjacent graphs independently checked',flush=True)


if __name__=='__main__':main()
