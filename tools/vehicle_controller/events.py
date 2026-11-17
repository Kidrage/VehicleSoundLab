"""Event audition controls; scheduling and synthesis stay in the C modules."""
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import json
from pathlib import Path
from event_authoring.contract import KINDS
from event_authoring.band_scope import normalize
from .event_profiles import document
from event_authoring.material_reviews import rejection,ensure_live_reference,without_rejected

NAMES=('启动啮合','启动拖转','接火补充','收油回火','换挡短声','起动机脱开','停机末响')


class EventPanel:
    def __init__(self,window,parent):
        self.window=window;self.enabled=tk.IntVar();self.buttons=[];self.status=tk.StringVar(value='尚未发声')
        self.model_info=tk.StringVar();self.info_kind=1
        left=ttk.Frame(parent);left.pack(side='left',fill='both',expand=True,padx=(0,22))
        right=ttk.Frame(parent);right.pack(side='left',fill='both',expand=True)
        ttk.Checkbutton(left,text='启用独立事件候选',variable=self.enabled).pack(anchor='w',pady=(0,12))
        imports=ttk.Frame(left);imports.pack(fill='x',pady=(0,10))
        ttk.Button(imports,text='导入事件 JSON',command=self.import_profile).pack(side='left')
        ttk.Button(imports,text='恢复默认事件',command=self.reset_profiles).pack(side='left',padx=6)
        self.remove_rejected=ttk.Button(left,text='移除已排除的参考',command=self.clear_rejected)
        self.remove_rejected.pack(anchor='w',pady=(0,10))
        ttk.Button(left,text='触发配方…',command=window.edit_event_policy).pack(anchor='w',pady=(0,10))
        ttk.Label(left,text='启用后替换旧回火／起动机和启动附加层。\n持续 DNA、低频和细节仍由原系统生成。',style='Hint.TLabel',wraplength=390).pack(anchor='w',pady=(0,14))
        window.slider(left,'event_gain','事件总电平',0,2)
        window.slider(left,'event_pitch','事件音高',.5,2)
        window.slider(left,'event_decay','事件时长／衰减',.25,4)
        window.slider(left,'event_texture','程序纹理比例',0,2)
        ttk.Label(left,text='音高、时长和纹理用于下一次触发；电平可以实时调。\n启动早期纹理的单次试听持续约 0.8 秒，之后淡出。',style='Hint.TLabel',wraplength=390).pack(anchor='w',pady=14)
        ttk.Label(left,textvariable=self.status,style='Hint.TLabel',wraplength=390).pack(anchor='w',pady=8)
        ttk.Label(right,text='单次试听与分类型电平',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=(0,10))
        for kind,name in enumerate(NAMES):
            row=ttk.Frame(right);row.pack(fill='x',pady=3)
            available=bool(self.available_mask()&(1<<kind))
            button=ttk.Button(row,text=name if available else name+' · 待素材',command=lambda k=kind:self.audition(k),width=22)
            button.pack(side='left');self.buttons.append(button)
            if not available:button.state(['disabled'])
            key='event_level_'+str(kind);variable=window.vars.setdefault(key,tk.DoubleVar())
            readout=tk.StringVar();window.values[key]=(readout,2)
            slider=ttk.Scale(row,variable=variable,from_=0,to=2);slider.pack(side='left',fill='x',expand=True,padx=8)
            ttk.Label(row,textvariable=readout,width=6,anchor='e').pack(side='right');window.widgets[key]=(slider,0)
        ttk.Label(right,textvariable=self.model_info,style='Hint.TLabel',wraplength=390).pack(anchor='w',pady=(12,0))
        ttk.Label(left,text='目前为素材驱动的试听候选，尚未获得音色验收。\n没有参数的类型保持禁用，不替换成通用爆音。',style='Hint.TLabel',wraplength=390).pack(anchor='w',pady=12)

    def load(self,control):
        w=self.window;c=control['events'];self.enabled.set(c['enabled'])
        for key in ('gain','pitch','decay','texture'):w.vars['event_'+key].set(c[key])
        for kind in range(7):
            key='event_level_'+str(kind);w.vars[key].set(c['levels'][kind])
            w.widgets[key][0].state(['!disabled'] if self.available_mask()&(1<<kind) else ['disabled'])
        self.refresh()

    def available_mask(self):
        mask=self.window.bridge.event_available_mask
        for kind,doc in self.window.event_overrides.items():
            if not rejection(doc):mask|=1<<KINDS.index(kind)
        return mask

    def refresh(self):
        w=self.window
        self.remove_rejected.state(['!disabled'] if any(rejection(doc) for doc in w.event_overrides.values()) else ['disabled'])
        for kind,button in enumerate(self.buttons):
            available=bool(self.available_mask()&(1<<kind));custom=KINDS[kind] in w.event_overrides
            excluded=custom and rejection(w.event_overrides[KINDS[kind]]) is not None
            button.configure(text=NAMES[kind]+(' · 已排除' if excluded else ' · 自定义' if custom else '' if available else ' · 待素材'))
            button.state(['!disabled'] if available else ['disabled'])
            w.widgets['event_level_'+str(kind)][0].state(['!disabled'] if available else ['disabled'])
        self.describe(self.info_kind)

    def describe(self,kind):
        self.info_kind=kind;key=KINDS[kind];w=self.window
        doc=w.event_overrides.get(key,w.bridge.event_profiles.get(key))
        if not doc:self.model_info.set(NAMES[kind]+'：尚无音色参数。');return
        parameters=doc.get('parameters',{})
        if not parameters.get('modes') and not parameters.get('bands'):
            self.model_info.set(NAMES[kind]+'：尚无音色参数，等待合适素材。')
            return
        review=rejection(doc)
        if review:
            self.model_info.set(str(doc.get('name',NAMES[kind]))[:90]+'\n已排除该参考：'+review['reason'])
            return
        try:
            job=doc.get('source_job',{});scope=normalize(job.get('analysis_scope'))
            band=(f"分析范围 {scope['low_hz']/1000:g}–{scope['high_hz']/1000:g} kHz；只作该频带补充。"
                  if scope['mode']=='band' else '全频参数候选。')
        except (AttributeError,TypeError,ValueError):band='分析范围标注无效，请核对导入工程。'
        cutoff=doc.get('parameters',{}).get('noise_lowpass_hz',0)
        if cutoff:band+=f' 噪声高切 {cutoff/1000:g} kHz，正弦模态保持。'
        contours=doc.get('parameters',{}).get('contours',[])
        if contours:band+=f' {len(contours)}组多段包络。'
        state='物理类型已标注' if doc.get('physical_identity_confirmed') is True else '物理类型尚未确认'
        self.model_info.set(str(doc.get('name',NAMES[kind]))[:90]+'\n'+band+'\n'+state+'；音色仍需试听。')

    def import_profile(self,path=None):
        w=self.window
        if w.running():w.message.set('请先停止监听，再导入事件；当前运行声源保持原参数。');return
        if path is None:path=filedialog.askopenfilename(parent=w.root,title='导入事件设计参数',filetypes=[('事件参数 JSON','*.json')])
        if not path:return
        try:
            doc=document(json.loads(Path(path).read_text(encoding='utf-8-sig')))
            ensure_live_reference({doc['kind']:doc})
            w.event_overrides[doc['kind']]=doc;self.info_kind=KINDS.index(doc['kind']);self.refresh()
            w.message.set('已导入 '+str(doc.get('name',doc['kind']))+'；下次监听生效，音高／时长／纹理仍由本窗口控制。')
        except Exception as error:w.message.set(str(error))

    def reset_profiles(self):
        w=self.window
        if w.running():w.message.set('请先停止监听，再恢复默认事件。');return
        w.event_overrides={};self.refresh();w.message.set('已恢复编译事件库；自定义参数已从当前工程移除。')

    def clear_rejected(self):
        w=self.window
        if w.running():w.message.set('请先停止监听，再移除已排除的参考。');return
        previous=w.event_overrides
        w.event_overrides=without_rejected(previous)
        for kind in set(previous)-set(w.event_overrides):w.vars['event_level_'+str(KINDS.index(kind))].set(0)
        self.refresh()
        w.message.set('已移除被否决的事件参考；启动与其他音色参数保留。回火等待新的素材。')

    def controls(self,control):
        w=self.window;value=dict(control['events']);value['enabled']=int(self.enabled.get())
        for key in ('gain','pitch','decay','texture'):value[key]=float(w.vars['event_'+key].get())
        value['levels']=[float(w.vars['event_level_'+str(kind)].get()) for kind in range(7)]
        return value

    def audition(self,kind):
        w=self.window
        self.describe(kind)
        if w.replaying:w.message.set('回放中保留原行程；请先停止监听，再单独试听。');return
        if not self.available_mask()&(1<<kind):return
        self.enabled.set(1);w.control['events']['manual_type']=kind;w.control['events']['manual_sequence']+=1
        if not w.running():w.start(monitor_only=True)
        w.message.set('单次试听：'+NAMES[kind]+'。可以在“低频与辅助层”页独奏事件声部。')

    def update(self,state):
        w=self.window
        for key in ('legacy_event_gain','startup_gain','catch_gain'):
            widget,feature=w.widgets[key]
            widget.state(['disabled'] if self.enabled.get() or feature and not w.features&feature else ['!disabled'])
        self.status.set(f"活动声部 {state.get('event_active',0)} / 4 · 峰值 {state.get('event_peak',0)}\n"
            f"已触发 {state.get('event_started',0)} · 容量拒绝 {state.get('event_rejected',0)}\n"
            f"排队 {state.get('event_queue',0)} · 队列溢出 {state.get('event_overflow',0)} · 身份日志丢失 {state.get('event_log_lost',0)}")
        stats=state.get('event_policy_stats',{})
        if stats:self.status.set(self.status.get()+f"\n合格收油 {stats.get('opportunities',0)} · 尝试组数 {stats.get('bursts_attempted',0)}"
            f"\n概率跳过 {stats.get('probability_skips',0)} · 冷却跳过 {stats.get('cooldown_skips',0)} · 缺音色 {stats.get('unavailable',0)}")
