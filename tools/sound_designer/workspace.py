"""Project I/O and authoring workflow, separate from measurements and C DSP."""
import base64
import csv
import io
import json
from pathlib import Path
import shutil
import uuid
import zipfile

import numpy as np
import soundfile as sf
from research_archive_v1 import sha
from sound_dna.profile import compile_file
from .analysis import measure
from . import models
from .render import preview


PRESETS={'v10':'V10 Exterior.model','warm':'Warm Additive.model','hollow':'Hollow Spectrum.model'}


class Workspace:
    def __init__(self,repo,root):
        self.repo,self.root=Path(repo),Path(root)
        self.root.mkdir(parents=True,exist_ok=True)

    def folder(self,identity):
        if not isinstance(identity,str) or len(identity)!=32 or any(c not in '0123456789abcdef' for c in identity):
            raise ValueError('无效工程编号')
        return self.root/identity

    def save(self,folder,value):
        temporary=folder/'project.pending.json'
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        temporary.replace(folder/'project.json')

    def load(self,identity):
        folder=self.folder(identity)
        return folder,json.loads((folder/'project.json').read_text(encoding='utf-8'))

    def view(self,identity):
        folder,p=self.load(identity)
        if (folder/'base.model').exists():
            m,base=models.read(folder/'base.model')
            p['model']=models.describe(m,base)
        p['id']=identity
        p['has_audio']=bool(p.get('audio_file') and (folder/p['audio_file']).is_file())
        p['reference_url']=f'/files/{identity}/reference.wav' if (folder/'reference.wav').exists() else None
        return p

    def parameters(self,identity):
        folder,p=self.load(identity);m,base=models.read(folder/'base.model')
        return dict(schema='vsl.sound-designer-preset/1',name=p['name'],root_hz=base,
                    base_profile={k:v.tolist() for k,v in m.items()},params=p['params'],
                    rows=p['rows'],rho=p['rho'],state=p['state'],viewpoint=p['viewpoint'],source=p['source'],
                    analysis=p['analysis'],selection=p.get('selection'))

    def projects(self):
        result=[]
        for file in sorted(self.root.glob('*/project.json'),key=lambda f:f.stat().st_mtime,reverse=True)[:50]:
            p=json.loads(file.read_text(encoding='utf-8'))
            result.append(dict(id=file.parent.name,name=p['name'],state=p['state']))
        return result

    def save_design(self,data):
        folder,p=self.load(data['id']);m,base=models.read(folder/'base.model')
        ctl=models.controls(data.get('params',{}))
        rows=data.get('rows');rho=data.get('rho')
        models.edit(m,base,ctl,rows,rho)
        p.update(name=str(data.get('name',p['name']))[:100],params=ctl,rows=rows,rho=rho,
                 state=data.get('state',p['state']),viewpoint=data.get('viewpoint',p['viewpoint']),preview_stale=True)
        self.save(folder,p)
        return self.view(data['id'])

    def create(self,data):
        identity=uuid.uuid4().hex;folder=self.folder(identity);folder.mkdir()
        p=dict(schema='vsl.sound-designer-project/1',name=str(data.get('name','未命名音色'))[:100],
               state=data.get('state','steady'),viewpoint=data.get('viewpoint','exterior'),
               params=dict(models.DEFAULTS),rows=None,rho=None,analysis=None,source=None)
        if 'preset' in data:
            if data['preset'] not in PRESETS: raise ValueError('未知预设')
            source=self.repo/'voices/dna_bank_v1'/PRESETS[data['preset']]
            shutil.copy2(source,folder/'base.model')
            p['name']=source.stem;p['source']=dict(kind='existing-model',file=str(source),sha256=sha(source))
        elif 'package' in data:
            package=data['package']
            if package.get('schema')!='vsl.sound-designer-preset/1': raise ValueError('不支持的预设文件')
            m={k:np.asarray(v,dtype=float) for k,v in package['base_profile'].items()}
            if 'basis' in m and 'rho' in m and m['rho'].shape==(0,) and m['basis'].ndim==2 and m['basis'].shape[1]==0:
                m['basis']=m['basis'].reshape(len(m['basis']),0,4)
            base=float(package['root_hz']);models.validate(m,base);models.write(folder/'base.model',m,base)
            p.update(name=str(package.get('name','导入音色'))[:100],params=models.controls(package['params']),
                     rows=package.get('rows'),rho=package.get('rho'),source=package.get('source'),
                     analysis=package.get('analysis'),selection=package.get('selection'),
                     state=package.get('state','custom'),viewpoint=package.get('viewpoint','unspecified'))
            models.edit(m,base,p['params'],p['rows'],p['rho'])
        else:
            raw=base64.b64decode(data['audio'],validate=True)
            if len(raw)>48*1024**2: raise ValueError('音频文件需小于48MB')
            suffix=Path(str(data['filename'])).suffix.lower()
            if suffix not in ('.wav','.flac','.aiff','.aif','.mp3','.ogg'): raise ValueError('请导入WAV、FLAC、AIFF、MP3或OGG')
            source=folder/('input'+suffix);source.write_bytes(raw)
            p['audio_file']=source.name
            info=sf.info(source)
            if info.channels not in (1,2) or not 8000<=info.samplerate<=192000 or not .4<=info.duration<=60:
                raise ValueError('需0.4–60秒、8–192kHz、单／双声道片段')
            audio,rate=sf.read(source,always_2d=True)
            p['analysis']=measure(audio,rate)
            sf.write(folder/'reference.wav',audio,rate,subtype='FLOAT')
            p['source']=dict(kind='audio',file=source.name,original_name=str(data['filename']),sha256=sha(source))
            p['name']=Path(str(data['filename'])).stem[:100]
            p['selection']=[0,len(audio)/rate]
        self.save(folder,p)
        return self.view(identity)

    def analyze(self,data):
        folder,p=self.load(data['id'])
        if not p.get('audio_file'): raise ValueError('此工程没有原音频，请重新导入参考片段')
        source=folder/p['audio_file'];info=sf.info(source)
        start,stop=float(data['start']),float(data['end'])
        if not np.isfinite([start,stop]).all() or not 0<=start<stop<=info.duration+.00001 or stop-start<.4:
            raise ValueError('请选择至少0.4秒的有效范围')
        audio,rate=sf.read(source,start=round(start*info.samplerate),stop=round(stop*info.samplerate),always_2d=True)
        root=data.get('root_hz')
        if root is not None and (not np.isfinite(float(root)) or not 5<=float(root)<=1000):
            raise ValueError('声学基频需在5–1000Hz内')
        p['analysis']=measure(audio,rate,root)
        p['selection']=[start,stop]
        sf.write(folder/'reference.wav',audio,rate,subtype='FLOAT')
        self.save(folder,p)
        return self.view(data['id'])

    def compile(self,data):
        folder,p=self.load(data['id']);root=float(data['root_hz'])
        if not p.get('audio_file'): raise ValueError('请先导入参考片段')
        if not np.isfinite(root) or not 5<=root<=1000: raise ValueError('请确认有效声学基频')
        if not p['analysis']: raise ValueError('请先分析参考音频')
        if not p['analysis']['stable_candidate'] and not data.get('allow_unstable',False):
            raise ValueError('片段音高有变化或周期证据不足。缩短选区，或明确选择“固定音色草稿”；分析表仍可导出。')
        h,k=data['harmonics'],data['components']
        if type(h) is not int or type(k) is not int or not 1<=h<=320 or not 0<=k<=16:
            raise ValueError('阶次1–320，联动成分0–16')
        output=folder/('compile_'+uuid.uuid4().hex)
        info=compile_file(folder/'reference.wav',output,root,p['name'],h,k)
        shutil.copy2(output/'voice.model',folder/'base.model')
        p.update(build=info,state=str(data.get('state','steady')),viewpoint=str(data.get('viewpoint','exterior')),
                 rows=None,rho=None,params=dict(models.DEFAULTS),
                 model_scope='固定音色统计参数；音高轨迹另存于分析，不自动转换成驾驶RPM映射')
        p.pop('last_version',None);p.pop('render_report',None)
        self.save(folder,p)
        return self.view(data['id'])

    def render(self,data):
        folder,p=self.load(data['id']);original,base=models.read(folder/'base.model')
        ctl=models.controls(data.get('params',{}))
        rows=data.get('rows');rho=data.get('rho')
        edited=models.edit(original,base,ctl,rows,rho)
        version=uuid.uuid4().hex;output=folder/version;output.mkdir()
        model_file=output/'voice.model';models.write(model_file,edited,base)
        report=preview(self.repo,model_file,output/'preview.wav',ctl)
        package=dict(schema='vsl.sound-designer-preset/1',name=str(data.get('name',p['name']))[:100],
                     root_hz=base,base_profile={k:v.tolist() for k,v in original.items()},params=ctl,
                     rows=rows,rho=rho,state=data.get('state',p['state']),viewpoint=data.get('viewpoint',p['viewpoint']),
                     source=p['source'],selection=p.get('selection'),analysis=p['analysis'],render_report=report,
                     gain_policy='gain_db已写入voice.model系数；调用C时使用unity gain，避免重复增益')
        (output/'parameters.json').write_text(json.dumps(package,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        table=models.describe(edited,base)['rows']
        with (output/'harmonics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
        (output/'analysis.json').write_text(json.dumps(p.get('analysis'),ensure_ascii=False,indent=2),encoding='utf-8')
        with zipfile.ZipFile(output/'sound-design.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for name in ('voice.model','parameters.json','harmonics.csv','analysis.json','preview.wav'):
                archive.write(output/name,name)
        p.update(name=package['name'],state=package['state'],viewpoint=package['viewpoint'],
                 params=ctl,rows=rows,rho=rho,last_version=version,render_report=report,preview_stale=False)
        self.save(folder,p)
        return dict(project=self.view(data['id']),audio=f'/files/{data["id"]}/{version}/preview.wav',
                    bundle=f'/files/{data["id"]}/{version}/sound-design.zip',
                    parameters=f'/files/{data["id"]}/{version}/parameters.json',
                    csv=f'/files/{data["id"]}/{version}/harmonics.csv')
