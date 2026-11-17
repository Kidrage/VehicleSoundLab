"""Audit frozen bytes and actual waveform isolation without the delivery builder."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.root.resolve();manifest=read(root/'manifest.json')
    declared=set()
    for row in manifest['files']:
        f=(root/row['path']).resolve();assert f.is_relative_to(root) and row['path'] not in declared
        declared.add(row['path']);assert f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
    assert declared|{'manifest.json'}=={f.relative_to(root).as_posix() for f in root.rglob('*') if f.is_file()}
    milestone=read(root/'repo/research/startup_timbre_v1_verification.json')
    assert milestone['result']=='passed' and not milestone['goal_complete'] and not milestone['timbre_accepted']
    binaries={sha(p) for p in (root/'binaries').rglob('*.dll')}
    for folder in ('regression1','delivery1','ui1'):
        base=root/'evidence'/folder;binding=read(base/'source_binding.json');assert binding['bridge_sha256'] in binaries
        for row in binding['files']:
            assert sha(base/'exact_sources'/row['path'])==row['sha256']==sha(root/'repo'/row['path'])
    source=root/'evidence/delivery1'
    x,rate=sf.read(source/'original/native.wav',dtype='float32',always_2d=True)
    y,other=sf.read(source/'candidate/native.wav',dtype='float32',always_2d=True)
    assert rate==other==48000 and x.shape==y.shape==(32*48000,23)
    assert np.array_equal(x[:,:19],y[:,:19]) and np.array_equal(x[144000:],y[144000:])
    assert not np.array_equal(x[:,19:],y[:,19:])
    mixes=[]
    weights=np.array([1,1,1,1,1,1,2**-.5,2**-.5,1,1,2**-.5,2**-.5,1,1,1,1,1,1,1,2**-.5,2**-.5,2**-.5,2**-.5])
    layout=milestone['delivery']['full_cycle_reports']['candidate']['native_stems']
    for name,packed in [('original',x),('candidate',y)]:
        mix,sr=sf.read(source/name/'mix.wav',dtype='float32',always_2d=True);assert sr==48000
        summed=np.zeros(mix.shape);offset=0
        for stem in layout:
            n=stem['channels'];part=packed[:,offset:offset+n].astype(float)
            summed+=part if n==2 else part*weights[offset];offset+=n
        assert np.max(abs(summed-mix))<2e-6
        assert np.max(abs(mix))<1 and np.max(abs(mix[31*48000:]))<1e-6
        mixes.append(mix)
    for row in milestone['delivery']['projects']['projects']:
        folder=root/'editable-projects'/row['id'];project=read(folder/'project.json')
        params=project['document']['parameters'];assert params['noise_lowpass_hz']==10000
        assert project['response_fit']=='source-response-v1'
        package=read(folder/project['last_version']/'parameters.json');assert package['document']['parameters']==params
        assert package['render_report']['renderer_sha256'] in binaries
    ui=milestone['ui'];assert ui['final_state']['underflows']==ui['restart_final_state']['underflows']==0
    assert len(milestone['regression']['cases'])==27 and len(milestone['voices_unchanged'])==89
    assert all(row['all_band_gates_pass'] for row in milestone['kernel']['material'])
    assert milestone['workbench']['compiled_C_header_all_fields_exact'] and milestone['workbench']['owned_server_closed']
    result=dict(result='passed',files=len(declared),bytes=sum(row['bytes'] for row in manifest['files']),
        manifest_sha256=sha(root/'manifest.json'),auditor_sha256=sha(__file__),
        complete_file_set_and_hashes=True,three_source_bindings_and_four_binaries=True,
        actual_32s_23channel_isolation=True,actual_mix_reconstruction=True,editable_projects_bound=True,
        goal_complete=False,timbre_accepted=False)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
