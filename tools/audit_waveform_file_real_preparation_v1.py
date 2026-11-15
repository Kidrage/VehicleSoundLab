"""Independent all-six real preparation, target profile and source/node identity."""
import argparse
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('workspace','study','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from observer_frequency_v1.reduced_oracle import synthesize
    from waveform_file_real_v1.audit_oracle import make
    repo=Path(__file__).resolve().parents[1]
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    r=dict(result='running',cases=[],maximum_errors={},inputs={})
    def check(name,x,y):
        x,y=np.asarray(x),np.asarray(y);assert x.shape==y.shape,(name,x.shape,y.shape)
        error=float(np.max(abs(x-y))/max(float(np.max(abs(y))),1.))
        r['maximum_errors'][name]=max(error,r['maximum_errors'].get(name,0.))
        assert error<2e-12,(name,error)
    try:
        source=load(a.study/'report.json')
        assert source['result']=='waveform_file_real_six_prepared' and len(source['cases'])==6
        assert source['all_resources_passed'] and source['retained_six_disk_passed']
        for name,digest in source['sources'].items():assert sha(repo/name)==sha(a.study/'exact_sources'/name)==digest
        for name,digest in source['inputs'].items():assert sha(name)==digest;r['inputs'][name]=digest
        for c in source['cases']:
            path=a.study/c['file'];assert sha(path)==c['sha256'];r['inputs'][str(path)]=sha(path)
            with np.load(path) as f:z={n:f[n] for n in f.files}
            with np.load(c['context_file']) as f:raw={n:f[n] for n in f.files}
            with np.load(c['original_files']['observer_source']) as old:
                assert np.array_equal(z['target'],old['audio'])
                assert np.array_equal(z['original_positions'],old['positions'])
                assert np.array_equal(z['target_source_coordinates'],old['coordinates'])
                assert np.array_equal(z['native'],old['native'])
            with np.load(c['original_files']['scale']) as old:assert np.array_equal(z['scale'],old['scale'])
            native,rate=sf.read(c['original_files']['native'],always_2d=True)
            assert rate==48000 and np.array_equal(native,z['native'])
            for key,rawkey in (('audio','audio'),('target','original_audio'),('source_coordinates','positions'),
                ('target_source_coordinates','original_positions'),('clock_times','clock_times'),('root_hz','root_hz'),
                ('source_start','source_start'),('aperture','aperture')):
                assert np.array_equal(z[key],raw[rawkey]),key
            assert np.array_equal(z['audio'][2048:-2048],z['target'])
            assert np.array_equal(z['orders'],np.arange(1,289))
            text=Path(c['order_source']).read_text(encoding='utf-8')
            assert 'WaveSynthesis(len(audio), positions, np.arange(1, 289))' in text
            orig=z['original_positions']
            expected=np.r_[np.arange(-2048,0,256),orig,orig[-1]+np.arange(256,2049,256)]+2048
            assert np.array_equal(z['positions'],expected) and expected[0]==0 and expected[-1]==len(z['audio'])-1
            oracle,old=make(z['audio'],z['target'],expected,z['orders'],z['scale'])
            for key,oldkey in (('weights','weights'),('sigma','sigma'),('amplitude','amplitude'),('band_power','band_power')):
                check('locked_'+key,z[key],old[oldkey])
            assert np.array_equal(z['floor_active'],old['floor_active'])
            wave=synthesize(oracle.nodes(z['probe_q'])*z['scale'][None],expected,z['orders'],len(z['audio']))
            check('full288_scalar_wave',z['probe_wave'],wave)
            check('complete_all_bin_spectrum',z['probe_spectrum'],oracle.spectral(wave))
            starts=np.arange(0,len(wave)-4096+1,256)
            slots=np.where((starts>=2048)&(starts+4096<=len(wave)-2048))[0]
            assert np.array_equal(slots,z['target_slots'])
            check('original_target_supported_rows',oracle.profile['rows'][slots],old['rows'])
            assert c['resources']['graph_transpose_three_owned_panels_counted']
            assert c['resources']['headroom_guard']==3*1024**3 and c['resources']['native_temporary_allowance']==3*1024**3//2
            r['cases'].append(dict(label=c['label'],all_qualified=True,original_arrays_bitwise_exact=True,
                orders=288,original_nodes=len(orig),extended_nodes=len(expected),original_target_rows=len(slots)))
            save(a.out/'report.json',r)
            print('AUDIT_REAL_PREP',c['label'],'PASS',flush=True)
        r.update(result='independent_waveform_file_real_preparation_verified',all_qualified=True,
            producer_sha256=sha(a.study/'report.json'),no_inverse_fit_or_C_or_hearing_promotion=True)
        save(a.out/'report.json',r)
    except BaseException as error:
        r.update(result='failed',error=repr(error));save(a.out/'report.json',r);raise


if __name__=='__main__':main()
