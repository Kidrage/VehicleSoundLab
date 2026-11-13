"""Index and freeze the isolated amplitude C port and exact legacy compatibility evidence."""
import argparse,csv,io,subprocess
from pathlib import Path
from research_archive_v1 import load,save,sha,freeze,verify,append_index
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--stage',choices=['index','freeze','verify'],required=True);a=p.parse_args()
repo=Path(__file__).resolve().parents[1];root=a.workspace/'baselines/modal_texture_c_v1'
evidence=a.workspace/'references/analysis/modal_texture_c_v1';parent=a.workspace/'baselines/modal_texture_v1'
old=load(parent/'inputs/C_files_sha256.json');voices=load(parent/'inputs/voice_files_sha256.json')
names=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z'],cwd=repo).decode().split('\0')
c={name:sha(repo/name) for name in sorted(set(names)) if name and Path(name).suffix.lower() in ['.c','.h']}
changed={name for name in old if old[name]!=c[name]};new=set(c)-set(old)
assert len(old)==569 and changed=={'modules/modal_source/voice.c','modules/modal_source/voice.h'}
assert len(new)==10 and len(c)==579
assert len(voices)==67 and all(sha(repo/name)==digest for name,digest in voices.items())
index=repo/'handoff/C文件索引.csv'


def indexed():
    rows=list(csv.reader(io.StringIO(index.read_text(encoding='utf-8-sig'))))
    assert all(len(row)==5 for row in rows);return {row[0]:row for row in rows[1:]}


if a.stage=='index':
    current=indexed();assert len(current)==569 and all(current[name][4]==digest for name,digest in old.items())
    lines=index.read_bytes().splitlines(keepends=True)
    for i,line in enumerate(lines[1:],1):
        name=next(csv.reader([line.decode('utf-8-sig')]))[0]
        if name in changed:lines[i]=line.replace(old[name].encode(),c[name].encode())
    buffer=io.StringIO(newline='');writer=csv.writer(buffer,lineterminator='\n')
    roles={'profile':'独立因子参数的有限域／奇异协方差校验','envelope':'新高斯AR／插值方差归一／正幅度／有限量平滑',
        'voice':'复用独立OSC，零量旁路且随机状态持续推进','io':'非实时版本化参数读取，失败不改变输出'}
    for name in sorted(new):
        if name.startswith('modules/'):
            row=[name,'独立声线幅度统计','modal_texture',roles[Path(name).stem],c[name]]
        else:row=[name,'怠速幅度核独立验证','modal_texture_v1','已知／原OSC兼容／控制契约' if Path(name).stem=='checks' else '持续C主声线FLOAT与增益导出；非完整细谱C移植',c[name]]
        writer.writerow(row)
    index.write_bytes(b''.join(lines)+buffer.getvalue().encode())
    print(dict(indexed=579,unchanged=567,modified=2,added=10));raise SystemExit

assert len(indexed())==579 and all(indexed()[name][4]==digest for name,digest in c.items())
if a.stage=='freeze':
    port=load(evidence/'verify1/report.json');reg=load(evidence/'regression1/report.json')
    assert port['result']=='isolated_C_amplitude_kernel_passed_pending_listening' and port['tests']==3
    assert reg['result']=='legacy_and_fixed_C_byte_compatibility_passed' and reg['tests']==59
    assert reg['WAV_exact']==84 and reg['CSV_exact']==3 and reg['fixed_idle_WAV_exact']==3
    sources=set(port['sources'])
    for report,prefix in [(port,'verify1'),(load(evidence/'regression1/full1/report.json'),'regression1/full1')]:
        for name,digest in report['sources'].items():
            assert sha(repo/name)==sha(evidence/prefix/'exact_sources'/name)==digest,name
            sources.add(name)
    sources.update(['tools/package_modal_texture_c_v1.py','tools/regress_modal_texture_c_v1.py',
        'modules/modal_texture/README.md','experiments/modal_texture_v1/F2_amplitude.mtexture',
        'research/怠速幅度纹理C核V1.md','handoff/算法说明.md','handoff/C模块与接口.md',
        'handoff/C文件索引.csv','handoff/研究续接.md','handoff/开发留痕.md','AGENTS.md'])
    assert sha(repo/'experiments/modal_texture_v1/F2_amplitude.mtexture')==sha(evidence/'verify1/F2/texture.mtexture')
    save(evidence/'C_files_sha256.json',c);save(evidence/'voice_files_sha256.json',voices)
    inputs={'C_files_sha256.json':evidence/'C_files_sha256.json','voice_files_sha256.json':evidence/'voice_files_sha256.json',
        'parent_profile.json':parent/'evidence/trial1/profile.json','parent_manifest.json':parent/'manifest.json',
        'data_workspace_AGENTS.md':a.workspace/'AGENTS.md'}
    validation=dict(schema='vsl.modal-texture-c-freeze/1',result='isolated_C_amplitude_port_and_legacy_checks_passed',
        git_parent=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        parent_manifest_sha256=sha(parent/'manifest.json'),source_modes=13,all_frozen_core_groups=9,
        hybrid_groups=9,known_groups=3,finite_ratio_groups=2,
        maximum_FS_error=port['maximum_FS_error'],maximum_gain_error=port['maximum_gain_error'],
        independent_CTests=3,driving_CTests=59,old_driving_WAV_byte_exact=84,old_driver_CSV_byte_exact=3,
        old_fixed_idle_WAV_byte_exact=3,C_H_total=579,C_H_unchanged=567,C_H_modified=2,C_H_added=10,
        voice_files_unchanged=67,amount_ramp_frames=864,zero_RNG_advance=True,NULL_old_arithmetic=True,
        all_C_full_mix=False,FIR_realtime_certified=False,driver_integrated=False,default_entry_changed=False,
        UI_changed=False,device_repeated=False,room=False,phase_modulation=False,frequency_modulation=False,
        listening_accepted=False,actual_RPM_load=False,shared_phase_qualified=False,old_players_preserved=True,
        listening_url='http://127.0.0.1:8789/references/analysis/modal_texture_v1/review1/index.html',
        next='Listen to the existing amplitude-only candidate, assess pumping and weak-line noise. Select fine-texture representation/cost separately before typed driver integration; preserve moving35 and source/RPM limits.')
    info=freeze(root,repo,sources,evidence,inputs,validation)
    save(repo/'research/modal_texture_c_v1_summary.json',dict(validation,freeze='baselines/modal_texture_c_v1',**info))
    append_index(repo/'handoff/阶段索引.csv',['modal_texture_c_v1','baselines/modal_texture_c_v1/manifest.json',
        str(info['file_count']),info['manifest_sha256'],'Isolated generic amplitude C kernel;3+59CTest;84WAV/3CSV/3fixedWAV exact',
        'Listening pending;FIR still Python;not driver/UI adoption or physical AM/RPM;old players preserved',
        'research/怠速幅度纹理C核V1.md | research/modal_texture_c_v1_summary.json',
        'baselines/modal_texture_c_v1/validation.json | baselines/modal_texture_c_v1/evidence/verify1/report.json'])
    print(info)
else:
    manifest=verify(root);summary=load(repo/'research/modal_texture_c_v1_summary.json')
    assert sha(root/'manifest.json')==summary['manifest_sha256']
    assert load(root/'inputs/C_files_sha256.json')==c and load(root/'inputs/voice_files_sha256.json')==voices
    assert sha(root/'source/tools/package_modal_texture_c_v1.py')==sha(Path(__file__))
    print(dict(verified=manifest['file_count'],C_H=579,voices=67))
