"""Projects, immutable history, fitting and real C previews for short events."""
from copy import deepcopy
import json
from pathlib import Path
import uuid
import numpy as np
import soundfile as sf
from author_event import author
from event_authoring.model import KINDS,validate
from event_authoring.native import Renderer,controls
from event_authoring.band_scope import normalize
from event_authoring.material_reviews import rejection
from sound_designer import history
from .media import import_audio,ranges
from .package import export,write_json
from . import context as event_context
from . import candidates as event_candidates


def identity(value):
    if not isinstance(value,str) or len(value)!=32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('无效事件工程编号')
    return value


def document(value):
    if not isinstance(value,dict) or value.get('schema') not in ('vsl.event-profile/1','vsl.event-profile/2','vsl.event-profile/3','vsl.event-profile/4') or value.get('kind') not in KINDS:
        raise ValueError('不支持的事件参数格式')
    validate(value['parameters'])
    if not value['parameters']['modes'] and not value['parameters']['bands']:raise ValueError('事件参数至少需要一个模态或噪声频带')
    return deepcopy(value)


class EventWorkspace:
    def __init__(self,repo,root):
        self.repo,self.root=Path(repo),Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.renderer=None

    def load(self,key):
        folder=self.root/identity(key)
        return folder,json.loads((folder/'project.json').read_text(encoding='utf-8'))

    def commit(self,folder,p,action):
        write_json(folder/'project.pending.json',p);(folder/'project.pending.json').replace(folder/'project.json')
        history.checkpoint(folder,p,action)
        return self.view(folder.name)

    def projects(self):
        result=[]
        for file in sorted(self.root.glob('*/project.json'),key=lambda f:f.stat().st_mtime_ns,reverse=True)[:80]:
            p=json.loads(file.read_text(encoding='utf-8'));result.append(dict(id=file.parent.name,name=p['name'],kind=p['kind']))
        return result

    def presets(self):
        bank=json.loads((self.repo/'voices/events_v1/profiles.json').read_text(encoding='utf-8'))
        return [dict(kind=k,name=v['name']) for k,v in bank['profiles'].items() if v['parameters']['modes'] or v['parameters']['bands']]

    def view(self,key):
        folder,p=self.load(key);p['id']=key
        p['material_review']=rejection(p['document']) if p.get('document') else None
        p['response_fit']=p.get('response_fit',(p.get('document') or {}).get('source_job',{}).get('response_fit','legacy'))
        p['envelope_fit']=p.get('envelope_fit',(p.get('document') or {}).get('source_job',{}).get('envelope_fit','legacy'))
        p['analysis_scope']=normalize(p.get('analysis_scope',(p.get('document') or {}).get('source_job',{}).get('analysis_scope')))
        base='/files/events/'+key+'/'
        p['source_url']=base+'master-monitor.wav' if p.get('audio') else None
        p['reference_url']=base+p['analysis_run']+'/reference-monitor.wav' if p.get('analysis_run') else None
        p['preview_url']=base+p['last_version']+'/preview.wav' if p.get('last_version') else None
        p['downloads']=base+p['last_version']+'/' if p.get('last_version') else None
        p['context_url']=base+p['context_run']+'/monitor.wav' if p.get('context_run') else None
        p['context_report_url']=base+p['context_run']+'/report.json' if p.get('context_run') else None
        p['scan_report_url']=base+p['scan_run']+'/report.json' if p.get('scan_run') else None
        p['context_matches_selection']=event_context.matches(p)
        origin=(p.get('document') or {}).get('provenance')
        background=(p.get('document') or {}).get('background')
        if origin and background and p.get('audio') and p.get('selection'):
            p['reference_matches_model']=(origin.get('sha256')==p['audio']['master_sha256'] and
                origin.get('first_frame')==round(p['selection'][0]*48000) and
                origin.get('last_frame')==round(p['selection'][1]*48000) and
                background.get('sha256')==p['audio']['master_sha256'] and
                background.get('first_frame')==round(p['background_selection'][0]*48000) and
                background.get('last_frame')==round(p['background_selection'][1]*48000) and
                normalize(p['document'].get('source_job',{}).get('analysis_scope'))==p['analysis_scope'])
        else:p['reference_matches_model']=None
        p['history']=[dict(id=v['id'],action=v['action'],created=v['created']) for v in
            (history.read(folder,f.stem) for f in history.entries(folder))]
        return p

    def create(self,data):
        key=uuid.uuid4().hex;folder=self.root/key;folder.mkdir()
        p=dict(schema='vsl.event-designer-project/1',name=str(data.get('name','未命名事件'))[:100],
            kind=data.get('kind','afterfire'),viewpoint=data.get('viewpoint','exterior'),context='',
            controls=controls({}),document=None,audio=None,analysis=None,preview_stale=True,analysis_scope=normalize())
        if 'preset' in data:
            bank=json.loads((self.repo/'voices/events_v1/profiles.json').read_text(encoding='utf-8'))
            p['document']=document(bank['profiles'][data['preset']]);p['kind']=p['document']['kind'];p['name']=p['document']['name']
            p['viewpoint']=p['document'].get('viewpoint','unspecified');p['context']=p['document'].get('context','')
        elif 'package' in data:
            package=data['package'];value=package.get('document') if package.get('schema')=='vsl.event-design/1' else package
            p['document']=document(value);p['kind']=value['kind'];p['name']=str(value['name'])[:100]
            p['controls']=controls(package.get('controls',{}))
            p['context']=str(value.get('context',''))[:2000];p['viewpoint']=str(value.get('viewpoint','unspecified'))[:80]
        else:
            p['audio']=import_audio(self.repo,folder,data);p['name']=Path(p['audio']['filename']).stem[:100]
            duration=p['audio']['duration'];cut=duration/2
            p['selection']=[cut,min(duration,cut+1.)];p['background_selection']=[0,cut]
        if p['document']:p['analysis_scope']=normalize(p['document'].get('source_job',{}).get('analysis_scope'))
        if p['kind'] not in KINDS:raise ValueError('未知事件类型')
        return self.commit(folder,p,'新建事件工程')

    def draft(self,p,data):
        q=deepcopy(p);q['name']=str(data.get('name',p['name']))[:100]
        q['scan_detector']=data.get('scan_detector',q.get('scan_detector','high'))
        if q['scan_detector'] not in ('high','low_mid','short_high'):raise ValueError('未知瞬态扫描类型')
        q['response_fit']=data.get('response_fit',q.get('response_fit',
            (q.get('document') or {}).get('source_job',{}).get('response_fit','legacy')))
        if q['response_fit'] not in ('legacy','source-response-v1','source-response-ensemble-v1'):raise ValueError('未知频谱响应校准方法')
        q['envelope_fit']=data.get('envelope_fit',q.get('envelope_fit',
            (q.get('document') or {}).get('source_job',{}).get('envelope_fit','legacy')))
        if q['envelope_fit'] not in ('legacy','band-attack-v1','band-contour-v1','band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5'):raise ValueError('未知起音提取方法')
        q['context']=str(data.get('context',p['context']))[:2000]
        q['viewpoint']=str(data.get('viewpoint',p['viewpoint']))[:80]
        kind=data.get('kind',p['kind'])
        if kind not in KINDS:raise ValueError('未知事件类型')
        q['kind']=kind;q['controls']=controls(data.get('controls',q['controls']))
        q['analysis_scope']=normalize(data.get('analysis_scope',q.get('analysis_scope',
            (q.get('document') or {}).get('source_job',{}).get('analysis_scope'))))
        if data.get('seconds') is not None:
            if not q.get('audio'):raise ValueError('参数工程没有可编辑的录音选区')
            q['selection'],q['background_selection']=ranges(data,q['audio']['duration'])
        if data.get('parameters') is not None:
            if q['document'] is None:raise ValueError('请先提取参数或导入事件预设')
            candidate=deepcopy(q['document']);candidate['parameters']=data['parameters'];document(candidate)
            if candidate['parameters'].get('noise_lowpass_hz',0):candidate['schema']='vsl.event-profile/2'
            if any(m.get('attack_seconds',0) for m in candidate['parameters']['modes']):candidate['schema']='vsl.event-profile/3'
            if candidate['parameters'].get('contours'):candidate['schema']='vsl.event-profile/4'
            if candidate['parameters']!=q['document']['parameters']:
                candidate['manually_edited']=True;candidate['status']='manually edited candidate; listening not accepted'
            q['document']=candidate
        if q['document']:
            q['document'].update(kind=kind,name=q['name'],context=q['context'],viewpoint=q['viewpoint'])
        q['preview_stale']=True
        return q

    def save(self,data):
        folder,p=self.load(data['id']);p=self.draft(p,data)
        return self.commit(folder,p,'保存事件参数')

    def probe_context(self,data):
        folder,p=self.load(data['id'])
        # Diagnostics retain any pending edit, but never fit, replace parameters,
        # change the event bank or require a successful acoustic contrast.
        run,report=event_context.make(folder,p,data)
        q=self.draft(p,data)
        q.update(selection=report['event_seconds'],background_selection=report['before_seconds'],
                 following_background_selection=report['after_seconds'],context_run=run,context_probe=report)
        q['preview_stale']=p.get('preview_stale',True) or q.get('document')!=p.get('document') or q['controls']!=p['controls']
        return self.commit(folder,q,'核查事件前后背景')

    def scan_candidates(self,data):
        folder,p=self.load(data['id'])
        q=self.draft(p,data)
        run,digest,report=event_candidates.make(folder,q)
        q.update(scan_run=run,scan_sha256=digest,candidate_scan=report)
        q.pop('selected_candidate',None)
        q['preview_stale']=p.get('preview_stale',True) or q.get('document')!=p.get('document') or q['controls']!=p['controls']
        return self.commit(folder,q,'扫描片段中的短瞬态')

    def use_candidate(self,data):
        folder,p=self.load(data['id'])
        row=event_candidates.selected(folder,p,data)
        q=self.draft(p,data)
        intervals=dict(data,seconds=row['event_seconds'],background_seconds=row['before_seconds'],
                       following_background_seconds=row['after_seconds'])
        run,report=event_context.make(folder,q,intervals)
        q.update(selection=row['event_seconds'],background_selection=row['before_seconds'],
                 following_background_selection=row['after_seconds'],context_run=run,context_probe=report,
                 selected_candidate=dict(scan_run=p['scan_run'],index=data['candidate_index'],**row))
        q['preview_stale']=p.get('preview_stale',True) or q.get('document')!=p.get('document') or q['controls']!=p['controls']
        return self.commit(folder,q,'选取瞬态并核查原声上下文')

    def analyze(self,data):
        folder,p=self.load(data['id'])
        if not p['audio']:raise ValueError('此参数工程没有原录音；请导入含背景的音频片段')
        selection,background=ranges(data,p['audio']['duration'])
        if type(data.get('gated',False)) is not bool:raise ValueError('持续门控选择必须为布尔值')
        p=self.draft(p,data)
        short=round(selection[1]*48000)-round(selection[0]*48000)<2880
        if short and (data.get('gated',False) or p.get('envelope_fit')!='legacy'):
            raise ValueError('短于60毫秒的事件请关闭持续门控和长窗起音提取；保留短事件幅度与衰减测量')
        if p.get('response_fit')=='source-response-ensemble-v1' and (p['analysis_scope']['mode']!='full' or p.get('envelope_fit')!='legacy'):
            raise ValueError('多次触发稳定提取目前需要全频和普通起落包络；关闭长窗包络提取')
        # Preserve edited parameters before a re-fit, including refused fits.
        self.commit(folder,p,'提取前保留编辑')
        if p.get('response_fit')=='source-response-v1' and p['analysis_scope']['mode']!='full':
            raise ValueError('频谱响应校准目前需要全频片段')
        if p.get('envelope_fit') in ('band-attack-v1','band-contour-v1','band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5') and (p.get('response_fit')!='source-response-v1' or p['analysis_scope']['mode']!='full'):
            raise ValueError('分频起音提取需要全频片段，并勾选频谱响应校准')
        job=dict(schema='vsl.event-authoring-job/11' if p.get('response_fit')=='source-response-ensemble-v1' else
            'vsl.event-authoring-job/10' if short else 'vsl.event-authoring-job/9' if p.get('envelope_fit')=='band-contour-v5' else
            'vsl.event-authoring-job/8' if p.get('envelope_fit')=='band-contour-v4' else
            'vsl.event-authoring-job/7' if p.get('envelope_fit')=='band-contour-v3' else
            'vsl.event-authoring-job/6' if p.get('envelope_fit')=='band-contour-v2' else
            'vsl.event-authoring-job/5' if p.get('envelope_fit')=='band-contour-v1' else
            'vsl.event-authoring-job/4' if p.get('envelope_fit')=='band-attack-v1' else
            'vsl.event-authoring-job/3' if p.get('response_fit')=='source-response-v1' else
            ('vsl.event-authoring-job/2' if p['analysis_scope']['mode']=='band' else 'vsl.event-authoring-job/1'),
            kind=p['kind'],name=p['name'],source=str(folder/'master.wav'),
            seconds=selection,background_seconds=background,gated=data.get('gated',False),
            physical_identity_confirmed=False,context=p['context'])
        if p['analysis_scope']['mode']=='band':job['analysis_scope']=p['analysis_scope']
        if p.get('response_fit') in ('source-response-v1','source-response-ensemble-v1'):job['response_fit']=p['response_fit']
        if p.get('envelope_fit') in ('band-attack-v1','band-contour-v1','band-contour-v2','band-contour-v3','band-contour-v4','band-contour-v5'):job['envelope_fit']=p['envelope_fit']
        run='analysis_'+uuid.uuid4().hex;jobfile=folder/(run+'.job.json');write_json(jobfile,job)
        result=author(jobfile,folder/run)
        clip,sr=sf.read(folder/run/'reference.wav',always_2d=True)
        sf.write(folder/run/'reference-monitor.wav',clip*.25,sr,subtype='FLOAT')
        p.update(selection=selection,background_selection=background,analysis_run=run,analysis=result)
        if result.get('status')=='analysis_only':
            p['observation']=json.loads((folder/run/'report.json').read_text(encoding='utf-8'))['observation']
        else:
            p['document']=document(json.loads((folder/run/'profile.json').read_text(encoding='utf-8')))
            p['document']['viewpoint']=p['viewpoint'];p['observation']=p['document']['observation']
            p['controls'].update(seconds=min(12,max(.2,selection[1]-selection[0]+.2)),hold_seconds=selection[1]-selection[0])
            p.pop('last_version',None);p.pop('render_report',None)
        return self.commit(folder,p,'仅保留分析' if result.get('status')=='analysis_only' else '提取事件参数')

    def render(self,data):
        folder,p=self.load(data['id']);p=self.draft(p,data)
        if not p['document']:raise ValueError('请先提取参数或载入候选预设')
        if self.renderer is None:self.renderer=Renderer(self.repo)
        x,report=self.renderer.render(p['document']['parameters'],p['kind'],p['controls'])
        version=uuid.uuid4().hex;output=folder/version;output.mkdir()
        sf.write(output/'synthesis.wav',x,48000,subtype='FLOAT')
        sf.write(output/'preview.wav',x*.25,48000,subtype='FLOAT')
        export(output,p['document'],p['controls'],report,event_context.export_evidence(p),event_candidates.export_evidence(p))
        p.update(last_version=version,render_report=report,preview_stale=False)
        return self.commit(folder,p,'生成C事件试听')

    def restore(self,data):
        folder,current=self.load(data['id']);value=history.read(folder,data['revision'])
        p=value['project']
        if p.get('schema')!='vsl.event-designer-project/1':raise ValueError('历史工程类型不匹配')
        self.commit(folder,current,'恢复前保留当前版本')
        return self.commit(folder,p,'恢复事件版本')
