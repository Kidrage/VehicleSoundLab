"""Compact independent controller window; no DSP or vehicle integration in UI."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

from .host import Host
from .native import Bridge,Engine
from . import take,startup,event_policy as policy,dna_bank as dna
from .events import EventPanel

MODES=('踏板驾驶','固定转速','自动演示','外部信号占位')
LIFE=('熄火','就绪','拖转','接火','运行','停机')
OPERATING=('怠速','空载补油','加速','巡航','收油','换挡切断','换挡恢复','降挡补油')
STEMS=('完整干声','DNA · 进气感声线','低频轰鸣','DNA · 空气纹理','旧进气模板','机械','旧排气空气模板','道路','风','启动纹理','接火补充','附加声源','旧事件／起动机',
       '事件声部 1','事件声部 2','事件声部 3','事件声部 4')
TONE=(
    ('低频与 DNA 细节源',(('detail','主声线幅度细节',0),('low_mix','互补低频分轨',0),('coherent_low_gain','相干低频',2),
                      ('resonant_gain','共振纹理源',4),('residual_gain','残差纹理源',1))),
    ('独立启停层',(('startup_gain','启动纹理',8),('catch_gain','接火补充',16),('legacy_event_gain','旧事件／起动机',0))),
    ('辅助模板 · 默认关闭',(('intake_gain','旧进气模板',0),('mechanical_gain','机械',0),('air_gain','旧排气空气模板',0),
                ('road_gain','道路',0),('wind_gain','风',0))))


class Window:
    def __init__(self,root,repo,workspace,library=None):
        self.root=root;self.repo=Path(repo);self.workspace=Path(workspace);self.bridge=Bridge(repo,library)
        self.host=None;self.keys=set();self.sequence=0;self.loaded=0;self.widgets={};self.last_error=None;self.replaying=False;self.pending_start=False
        self.event_overrides={}
        self.startup_response=deepcopy(self.bridge.startup_defaults);self.startup_panel=None
        self.event_policy=deepcopy(self.bridge.event_policy_defaults);self.policy_panel=None
        self.dna_bank=None;self.dna_panel=None;self.dna_status=tk.StringVar(value='目录声纹')
        self.root.title('VEHICLE SOUND · 统一 DNA V15');self.root.geometry('1100x860');self.root.minsize(1020,800)
        self.root.configure(bg='#f2f4f7');style=ttk.Style(root);style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10),background='#f2f4f7',foreground='#172338')
        style.configure('TFrame',background='#f2f4f7');style.configure('TLabelframe',padding=14)
        style.configure('TButton',padding=(12,8));style.configure('Primary.TButton',background='#215fcd',foreground='white')
        style.map('Primary.TButton',background=[('active','#174ba8')]);style.configure('Header.TLabel',font=('Segoe UI',20,'bold'))
        style.configure('Readout.TLabel',font=('Segoe UI',25,'bold'));style.configure('Hint.TLabel',foreground='#667387',font=('Microsoft YaHei UI',9))
        outer=ttk.Frame(root,padding=22);outer.pack(fill='both',expand=True)
        header=ttk.Frame(outer);header.pack(fill='x');ttk.Label(header,text='VEHICLE SOUND',style='Header.TLabel').pack(side='left')
        ttk.Label(header,text='驾驶与声源控制  /  纯合成 · 干声',style='Hint.TLabel').pack(side='right')
        selection=ttk.Frame(outer);selection.pack(fill='x',pady=(18,14))
        self.preset=tk.StringVar();self.preset_box=ttk.Combobox(selection,textvariable=self.preset,state='readonly',width=55,
            values=[row['name'] for row in self.bridge.catalog]);self.preset_box.pack(side='left',fill='x',expand=True)
        self.preset_box.bind('<<ComboboxSelected>>',lambda e:self.load(self.preset_box.current()))
        ttk.Button(selection,text='载入参数',command=self.restore).pack(side='left',padx=(8,0))
        ttk.Button(selection,text='保存参数',command=self.save).pack(side='left',padx=(8,0))
        self.tabs=ttk.Notebook(outer);self.tabs.pack(fill='both',expand=True)
        self.drive=ttk.Frame(self.tabs,padding=18);self.tone=ttk.Frame(self.tabs,padding=18);self.signals=ttk.Frame(self.tabs,padding=18)
        self.events_page=ttk.Frame(self.tabs,padding=18);self.dna_page=ttk.Frame(self.tabs,padding=18)
        self.tabs.add(self.drive,text=' 驾驶 ');self.tabs.add(self.dna_page,text=' DNA 配方 ');self.tabs.add(self.tone,text=' 低频与辅助层 ');self.tabs.add(self.events_page,text=' 独立事件 ');self.tabs.add(self.signals,text=' 信号与回放 ')
        self.vars={};self.values={};self.mode=tk.StringVar(value=MODES[0]);self.automatic=tk.IntVar(value=1);self.backfire=tk.IntVar(value=1)
        self.gear=tk.IntVar(value=1);self.solo=tk.StringVar(value=STEMS[0]);self.muted=tk.IntVar();self.pause_signals=tk.IntVar()
        self.message=tk.StringVar(value='选择音色，点击“启动”开始；更换音色前停止监听。')
        self.status=tk.StringVar(value='尚未启动');self.rpm=tk.StringVar(value='0');self.speed=tk.StringVar(value='0.0');self.state=tk.StringVar(value='熄火')
        self.detail_status=tk.StringVar(value='');self._build_drive();self._build_tone();self._build_signals()
        self.event_panel=EventPanel(self,self.events_page)
        from .startup_sound_panel import StartupSoundPanel
        self.startup_sound=StartupSoundPanel(self,self.drive_side)
        ttk.Label(outer,textvariable=self.message,style='Hint.TLabel',wraplength=950).pack(fill='x',pady=(14,0))
        root.bind('<KeyPress>',self.key_down);root.bind('<KeyRelease>',self.key_up);root.bind('<FocusOut>',self.focus_out)
        root.bind('<Unmap>',lambda event:self.release_keyboard() if event.widget is root else None)
        root.protocol('WM_DELETE_WINDOW',self.close);self.load(0);root.after(40,self.tick)

    def slider(self,parent,key,label,low=0,high=1,feature=0,row_padding=5):
        row=ttk.Frame(parent);row.pack(fill='x',pady=row_padding);variable=self.vars.setdefault(key,tk.DoubleVar())
        ttk.Label(row,text=label,width=19).pack(side='left');readout=tk.StringVar();self.values[key]=(readout,high)
        widget=ttk.Scale(row,variable=variable,from_=low,to=high);widget.pack(side='left',fill='x',expand=True,padx=8)
        ttk.Label(row,textvariable=readout,width=8,anchor='e').pack(side='right');self.widgets[key]=(widget,feature)
        return widget

    def _build_drive(self):
        left=ttk.Frame(self.drive);left.pack(side='left',fill='both',expand=True,padx=(0,24));right=ttk.Frame(self.drive,width=260);right.pack(side='right',fill='y')
        self.drive_side=right
        actions=ttk.Frame(left);actions.pack(fill='x',pady=(0,18))
        self.start_button=ttk.Button(actions,text='启动',style='Primary.TButton',command=self.start);self.start_button.pack(side='left')
        self.ignition_button=ttk.Button(actions,text='熄火',command=self.ignition_off)
        self.ignition_button.pack(side='left',padx=8)
        ttk.Button(actions,text='停止监听',command=self.stop).pack(side='left')
        self.demo_button=ttk.Button(actions,text='完整流程',command=self.demo)
        self.demo_button.pack(side='left',padx=(8,0))
        self.startup_button=ttk.Button(left,text='启动与停机响应…',command=self.edit_startup)
        self.startup_button.pack(anchor='w',pady=(0,10))
        mode_box=ttk.Combobox(left,textvariable=self.mode,values=MODES,state='readonly')
        mode_box.pack(fill='x',pady=(0,12))
        self.slider(left,'throttle','油门');self.slider(left,'brake','刹车')
        row=ttk.Frame(left);row.pack(fill='x',pady=14)
        auto_box=ttk.Checkbutton(row,text='运动自动挡',variable=self.automatic);auto_box.pack(side='left')
        ttk.Label(row,text='手动挡位').pack(side='left',padx=(18,5))
        gear_box=ttk.Spinbox(row,from_=0,to=7,width=4,textvariable=self.gear,state='readonly');gear_box.pack(side='left')
        self.slider(left,'gain','输出电平')
        backfire_box=ttk.Checkbutton(left,text='允许收油回火（电平见音色页）',variable=self.backfire)
        backfire_box.pack(anchor='w',pady=8)
        self.drive_widgets=(mode_box,auto_box,gear_box,backfire_box,self.start_button,self.ignition_button,self.demo_button)
        ttk.Label(left,text='W 油门 · S 刹车 · Q / E 换挡\n释放按键后回落；窗口失焦释放键盘踏板。',style='Hint.TLabel').pack(anchor='w',pady=12)
        for label,var,unit in (('虚拟发动机',self.rpm,'RPM'),('车辆速度',self.speed,'km/h')):
            ttk.Label(right,text=label,style='Hint.TLabel').pack(anchor='w');ttk.Label(right,textvariable=var,style='Readout.TLabel').pack(anchor='w')
            ttk.Label(right,text=unit,style='Hint.TLabel').pack(anchor='w',pady=(0,14))
        ttk.Label(right,textvariable=self.state,font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',pady=10)
        ttk.Label(right,textvariable=self.detail_status,wraplength=240,style='Hint.TLabel').pack(anchor='w')

    def _build_tone(self):
        from .dna_tone_panel import DnaTonePanel
        bar=ttk.Frame(self.dna_page);bar.pack(fill='x',pady=(0,12))
        self.dna_button=ttk.Button(bar,text='导入／编辑声纹…',command=self.edit_dna);self.dna_button.pack(side='left')
        ttk.Combobox(bar,textvariable=self.solo,values=STEMS,state='readonly',width=21).pack(side='right')
        ttk.Label(bar,textvariable=self.dna_status,style='Hint.TLabel',wraplength=680).pack(side='left',padx=16)
        body=ttk.Frame(self.dna_page);body.pack(fill='both',expand=True);self.dna_tone=DnaTonePanel(body)
        columns=[]
        for _ in range(2):
            col=ttk.Frame(self.tone);col.pack(side='left',fill='both',expand=True,padx=6);columns.append(col)
        for i,(title,rows) in enumerate(TONE):
            group=ttk.LabelFrame(columns[0 if i==0 else 1],text=title);group.pack(fill='x',pady=(0,12))
            for key,label,feature in rows:self.slider(group,key,label,feature=feature,row_padding=2)
        ttk.Label(columns[0],text='先在 DNA 配方页调声线与纹理，再调低频。\n本页细节源送入同一个 DNA 纹理总线。',wraplength=390,style='Hint.TLabel').pack(anchor='w',pady=8)
        ttk.Label(columns[0],text='独奏监听',font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w',pady=(12,8))
        ttk.Combobox(columns[0],textvariable=self.solo,values=STEMS,state='readonly').pack(fill='x')
        self.mute_box=ttk.Checkbutton(columns[0],text='监听静音（生成继续）',variable=self.muted)
        self.mute_box.pack(anchor='w',pady=10)
        ttk.Label(columns[0],text='旧回火／起动机是历史工程声源；新事件音色正在另行制作。',wraplength=350,style='Hint.TLabel').pack(anchor='w',pady=8)

    def _build_signals(self):
        self.slider(self.signals,'external_speed','输入速度 · km/h',0,360)
        self.slider(self.signals,'external_acceleration','输入加速度 · m/s²',-15,15)
        self.slider(self.signals,'tire_slip','打滑强度')
        self.slider(self.signals,'rpm','固定转速 · RPM',850,10000)
        self.slider(self.signals,'load','固定负载',-1,1)
        ttk.Checkbutton(self.signals,text='暂停外部信号更新（测试超时）',variable=self.pause_signals).pack(anchor='w',pady=12)
        ttk.Label(self.signals,text='外部模式采用输入速度／加速度，RPM 由虚拟传动映射生成。\n踏板模式使用内部车辆模型；固定转速模式直接控制 RPM 与负载。\n打滑会参与外部虚拟转速映射，独立轮胎音色尚未接入。',style='Hint.TLabel').pack(anchor='w',pady=6)
        buttons=ttk.Frame(self.signals);buttons.pack(fill='x',pady=16)
        ttk.Button(buttons,text='保存本次行程',command=self.save_take).pack(side='left')
        ttk.Button(buttons,text='回放行程',command=self.open_take).pack(side='left',padx=8)
        ttk.Label(self.signals,textvariable=self.status,style='Hint.TLabel',wraplength=850).pack(anchor='w')

    def load(self,selection,dna_bank=None):
        if self.running():return
        bank=dna.validate(dna_bank)
        control,features=self.bridge.initial(selection,bank)
        if selection==0 and bank is None:
            from .startup_sound import defaults
            control=defaults(control,self.bridge.event_available_mask)
        if self.startup_panel:self.startup_panel.close()
        if self.policy_panel:self.policy_panel.close()
        self.startup_response=deepcopy(self.bridge.startup_defaults)
        self.event_policy=deepcopy(self.bridge.event_policy_defaults)
        self.control,self.features=control,features;self.loaded=selection;self.preset_box.current(selection)
        if bank:self.preset.set('工作台 DNA · '+bank['name'])
        self.dna_bank=bank;self.dna_status.set(dna.coverage(bank))
        self.dna_tone.load(control['dna']);self.dna_tone.refresh(features)
        for key,variable in self.vars.items():variable.set(self.control.get(key,0))
        self.vars['rpm'].set(self.control['rpm']);self.gear.set(self.control['gear']);self.automatic.set(self.control['automatic'])
        self.backfire.set(self.control['backfire']);self.sequence=0
        for widget,feature in self.widgets.values():widget.state(['!disabled'] if not feature or self.features&feature else ['disabled'])
        self.event_panel.load(self.control)

    def edit_dna(self):
        if self.running():self.message.set('请先停止监听，再编辑DNA声源。');return
        if self.dna_panel:self.dna_panel.root.lift();return
        from .dna_panel import DnaPanel
        self.dna_panel=DnaPanel(self)

    def apply_dna(self,bank):
        if self.running():raise ValueError('请先停止监听，再应用DNA声源')
        self.load(self.loaded,bank)
        self.event_overrides={}
        self.event_panel.refresh()
        self.message.set('DNA已应用。自定义声纹不继承其他车型的细谱纹理；空纹理槽保持静音，独立事件另选。')

    def display_controls(self,value,mode):
        self.control=deepcopy(value);self.mode.set(mode)
        self.dna_tone.load(value['dna'])
        for key,var in self.vars.items():
            if key in value:var.set(value[key])
        self.automatic.set(value['automatic']);self.backfire.set(value['backfire']);self.gear.set(value['gear'])
        signals=value['input'];self.sequence=signals['sequence'];self.signal=deepcopy(signals)
        self.vars['external_speed'].set(signals['speed_mps']*3.6)
        self.vars['external_acceleration'].set(signals['acceleration_mps2']);self.vars['tire_slip'].set(signals['tire_slip'])
        self.event_panel.load(value)

    def running(self):return self.host is not None and self.host.thread is not None and self.host.thread.is_alive()

    def edit_startup(self):
        if self.running():self.message.set('请先停止监听，再编辑启动响应。');return
        if self.startup_panel:self.startup_panel.root.lift();return
        from .startup_panel import StartupPanel
        self.startup_panel=StartupPanel(self)

    def controls(self):
        value=deepcopy(self.control)
        value['dna']=self.dna_tone.get()
        for key in value:
            if key in self.vars:value[key]=float(self.vars[key].get())
        value.update(gear=int(self.gear.get()),automatic=self.automatic.get(),backfire=self.backfire.get())
        mode=self.mode.get();value['mode']=0 if mode==MODES[1] else 2 if mode==MODES[2] else 1
        external=mode==MODES[3]
        if not (external and self.pause_signals.get()):
            self.sequence+=1
            self.signal=dict(source=int(external),valid=7 if external else 4,sequence=self.sequence,
                speed_mps=self.vars['external_speed'].get()/3.6 if external else 0,
                acceleration_mps2=self.vars['external_acceleration'].get() if external else 0,tire_slip=self.vars['tire_slip'].get())
        value['input']=deepcopy(getattr(self,'signal',self.control['input']))
        value['events']=self.event_panel.controls(self.control)
        return value

    def edit_event_policy(self):
        if self.running():self.message.set('请先停止监听，再编辑事件触发配方。');return
        if self.policy_panel:self.policy_panel.root.lift();return
        from .event_policy_panel import EventPolicyPanel
        self.policy_panel=EventPolicyPanel(self)

    def start(self,replay=None,monitor_only=False):
        if replay is None:
            from event_authoring.material_reviews import ensure_live_reference
            try:ensure_live_reference(self.event_overrides)
            except ValueError as error:self.message.set(str(error));return
        if self.running():
            if not self.replaying:
                if self.host.snapshot().get('lifecycle')==5:
                    self.pending_start=True;self.message.set('停机完成后重新启动。')
                else:self.control['ignition']=1;self.control['start_id']+=1
            return
        self.last_error=None;self.replaying=replay is not None
        if self.startup_panel:self.startup_panel.close()
        if self.policy_panel:self.policy_panel.close()
        if self.dna_panel:self.dna_panel.close()
        if replay:
            self.event_overrides=deepcopy(replay['event_overrides'])
            self.load(replay['catalog']['id'],replay.get('dna_bank'));value=replay['initial']
            self.startup_response=startup.validate(replay['startup_response'])
            self.event_policy=policy.configuration(self.bridge,replay.get('event_policy'))
            self.display_controls(value,MODES[3] if value['input']['source'] else {0:MODES[1],1:MODES[0],2:MODES[2]}[value['mode']])
        else:
            if not monitor_only:self.control['ignition']=1;self.control['start_id']+=1
            else:self.control['ignition']=0
            value=self.controls()
        self.host=Host(self.bridge,self.loaded,value,replay,self.event_overrides,self.startup_response,self.event_policy,self.dna_bank)
        self.host.update(value,STEMS.index(self.solo.get())-1,bool(self.muted.get()))
        self.host.start();self.preset_box.state(['disabled'])
        self.message.set('正在回放记录的 C 控制信号。' if replay else '正在监听纯合成干声；空间渲染由外部系统处理。')

    def demo(self):
        if self.running():self.message.set('请先停止监听，再播放完整流程。');return
        from vehicle_scenarios.start_idle import start_idle_lifecycle
        try:
            value,_=start_idle_lifecycle(self.bridge,self.loaded,self.controls(),self.event_overrides,self.startup_response,self.event_policy,self.dna_bank)
            self.pending_start=False;self.start(value)
            self.message.set('36秒完整流程：启动 → 怠速 → 加速 → 收油 → 制动降挡 → 停车怠速 → 熄火。采用播放前的音色设置；播放中可切换独奏。')
        except Exception as error:self.message.set(str(error))

    def ignition_off(self):
        self.pending_start=False
        if not self.replaying:self.control['ignition']=0;self.vars['throttle'].set(0);self.vars['brake'].set(0);self.keys.clear()

    def stop(self):
        if self.host:self.host.stop()
        self.pending_start=False
        self.keys.clear();self.vars['throttle'].set(0);self.vars['brake'].set(0)

    def key_down(self,event):
        if self.replaying or isinstance(self.root.focus_get(),(ttk.Entry,ttk.Combobox,ttk.Spinbox,tk.Entry)):return
        key=event.keysym.lower()
        if key not in self.keys and key in ('q','e'):
            self.automatic.set(0);self.gear.set(max(0,min(7,self.gear.get()+(1 if key=='e' else -1))))
        self.keys.add(key)

    def key_up(self,event):
        self.keys.discard(event.keysym.lower())
        if event.keysym.lower() in ('w','s'):self.vars['throttle' if event.keysym.lower()=='w' else 'brake'].set(0)

    def focus_out(self,event):
        if event.widget is self.root:self.release_keyboard()
        else:self.root.after_idle(self.release_if_unfocused)

    def release_keyboard(self):
        if self.keys:self.keys.clear();self.vars['throttle'].set(0);self.vars['brake'].set(0)

    def release_if_unfocused(self):
        if not self.root.winfo_viewable() or self.root.focus_displayof() is None:self.release_keyboard()

    def replay_controls(self,active):
        self.dna_tone.lock(active)
        self.startup_sound.lock(active)
        for widget,feature in self.widgets.values():
            widget.state(['disabled'] if active or feature and not self.features&feature else ['!disabled'])
        for widget in self.drive_widgets:widget.state(['disabled'] if active else ['!disabled'])
        if not active:self.event_panel.refresh()

    def tick(self):
        try:
            self.dna_tone.refresh(self.features)
            self.startup_sound.refresh()
            self.startup_button.state(['disabled'] if self.running() else ['!disabled'])
            self.dna_button.state(['disabled'] if self.running() else ['!disabled'])
            if 'w' in self.keys:self.vars['throttle'].set(min(1,self.vars['throttle'].get()+.07))
            if 's' in self.keys:self.vars['brake'].set(min(1,self.vars['brake'].get()+.10))
            for key,(text,high) in self.values.items():
                value=self.vars[key].get()
                text.set(f'{value:.2f}×' if key in ('event_pitch','event_decay') else f'{value*100:.0f}%' if key.startswith('event_') or high<=1 else f'{value:.0f}')
            if self.running():
                self.host.update(self.control if self.replaying else self.controls(),STEMS.index(self.solo.get())-1,bool(self.muted.get()))
            if self.host:
                state=self.host.snapshot()
                if self.replaying and 'adopted_control' in state:
                    value=state['adopted_control']
                    self.display_controls(value,MODES[3] if value['input']['source'] else {0:MODES[1],1:MODES[0],2:MODES[2]}[value['mode']])
                active_replay=self.replaying and self.running()
                self.replay_controls(active_replay)
                self.event_panel.update(state)
                if active_replay:self.replay_controls(True)
                if self.pending_start and state.get('lifecycle')==0:
                    self.control['ignition']=1;self.control['start_id']+=1;self.pending_start=False
                if 'rpm' in state:
                    self.rpm.set(f"{state['rpm']:,.0f}");self.speed.set(f"{state['speed_mps']*3.6:.1f}")
                    label=LIFE[state['lifecycle']]
                    if state['lifecycle']==4:label+=' · '+OPERATING[state['operating']]
                    self.state.set(label+(' · 监听停止' if not state['active'] else ''))
                    self.detail_status.set(f"挡位 {state['gear'] or 'N'}  ·  负载 {state['load']:.2f}\n声学根音 {state['root_hz']:.1f} Hz\n换挡 {state['shifts']}  /  收油 {state['overruns']}\n"+
                        ('信号超时：速度保持、踏板释放' if state['input_stale'] else '外部信号有效' if state['input_source'] else '内部车辆模型'))
                    if self.dna_bank and self.dna_bank.get('states'):
                        from .dna_states import describe_blend
                        self.dna_status.set(dna.coverage(self.dna_bank)+'\n'+describe_blend(state.get('dna_state')))
                    self.status.set(f"生成 {state['frame']/48000:.1f} s  ·  供声中断 {state['underflows']} 次  ·  PC 块耗时 {state['pc_block_load']*100:.0f}%（不代表 SHARC 算力）")
                if state.get('error') and state['error']!=self.last_error:self.last_error=state['error'];self.message.set('运行错误：'+state['error'])
                if not self.running():self.preset_box.state(['!disabled','readonly']);self.replaying=False
        except Exception as error:self.message.set(str(error))
        self.root.after(40,self.tick)

    def save(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='保存音色与控制参数',defaultextension='.json',filetypes=[('参数 JSON','*.json')])
        if path:
            try:
                value=self.controls();value['events']['manual_sequence']=0
                from .recipe import create
                take.save(path,create(self.bridge,self.loaded,value,self.mode.get(),self.event_overrides,self.startup_response,self.event_policy,self.dna_bank))
                self.message.set('参数已保存：'+path)
            except Exception as error:self.message.set(str(error))

    def restore(self):
        if self.running():self.message.set('请先停止监听，再载入参数。');return
        path=filedialog.askopenfilename(parent=self.root,title='载入参数',filetypes=[('参数 JSON','*.json')])
        if not path:return
        try:
            value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if value.get('schema') not in ('vsl.source-controller-preset/1','vsl.source-controller-preset/2','vsl.source-controller-preset/3','vsl.source-controller-preset/4','vsl.source-controller-preset/5','vsl.source-controller-preset/6','vsl.source-controller-preset/7','vsl.source-controller-preset/8','vsl.source-controller-preset/9'):raise ValueError('参数格式不匹配')
            if value['mode'] not in MODES:raise ValueError('控制模式无效')
            from .recipe import validate
            overrides=validate(self.bridge,value)
            # Native validation completes before replacing the window state.
            with Engine(self.bridge,value['catalog'],overrides,value.get('startup_response'),value.get('event_policy'),value.get('dna_bank')) as probe:
                probe.set(value['control'])
            self.load(value['catalog'],value.get('dna_bank'));self.event_overrides=overrides
            self.startup_response=startup.configuration(self.bridge,value.get('startup_response'))
            self.event_policy=policy.configuration(self.bridge,value.get('event_policy'))
            if value['schema']=='vsl.source-controller-preset/1':value['control']['events']=deepcopy(self.control['events'])
            self.display_controls(value['control'],value['mode'])
            self.message.set('参数已载入。' if value['control']['events']['enabled'] else '参数已载入；此配方关闭了独立事件，驾驶页可启用启动音。')
        except Exception as error:self.message.set(str(error))

    def save_take(self):
        if not self.host or not self.host.take_snapshot()['frames']:self.message.set('请先启动并生成一段声音。');return
        self.workspace.mkdir(parents=True,exist_ok=True)
        path=self.workspace/(datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.vsltake.json')
        take.save(path,self.host.take_snapshot());self.message.set('行程已保存：'+str(path))

    def open_take(self):
        if self.running():self.message.set('请先停止监听，再回放行程。');return
        path=filedialog.askopenfilename(parent=self.root,title='回放行程',initialdir=self.workspace,filetypes=[('控制行程','*.vsltake.json')])
        if path:
            try:self.start(take.read(path,self.bridge))
            except Exception as error:self.message.set(str(error))

    def close(self):
        self.stop()
        def finish():
            if self.running():self.root.after(30,finish)
            else:self.root.destroy()
        finish()


def run(repo,workspace,ready_file=None,library=None):
    root=tk.Tk()
    try:window=Window(root,repo,workspace,library)
    except Exception as error:messagebox.showerror('VEHICLE SOUND',str(error),parent=root);root.destroy();raise
    root.update_idletasks()
    if ready_file:
        import os
        take.save(ready_file,dict(schema='vsl.source-controller-ready/1',pid=os.getpid(),title=root.title(),
            bridge_sha256=window.bridge.sha256,voices_sha256=window.bridge.voices_sha256,
            catalog_assets_sha256=window.bridge.catalog_assets_sha256,ui_revision=15,preset_schema=9,take_schema=10,
            event_bank_sha256=window.bridge.event_bank_sha256,abi=window.bridge.abi(),
            geometry=root.geometry(),source_only=True,listening=window.running()))
    root.mainloop()
