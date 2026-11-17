"""Non-live trigger recipe editor; scheduling stays in event_control C."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk
from . import event_policy as policy


class EventPolicyPanel:
    def __init__(self,owner):
        self.owner=owner;self.vars={};self.inputs={}
        self.root=tk.Toplevel(owner.root);self.root.title('事件触发配方')
        self.root.geometry('640x680');self.root.resizable(False,False);self.root.transient(owner.root)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        body=ttk.Frame(self.root,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text='事件触发配方',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        ttk.Label(body,text='控制何时触发、连发次数及间隔；停止监听后应用。\n音色的模态、纹理与衰减仍在事件设计页编辑。',
            style='Hint.TLabel',wraplength=590).pack(anchor='w',pady=(8,12))
        for key,label,low,high,step,default in policy.FIELDS:
            if not owner.bridge.tuning_headroom and key not in ('afterfire_min_count','afterfire_max_count','afterfire_probability'):high=round(high/1.3,8)
            row=ttk.Frame(body);row.pack(fill='x',pady=4)
            ttk.Label(row,text=label,width=29).pack(side='left')
            var=tk.StringVar(value=f'{owner.event_policy[key]:g}');self.vars[key]=var
            box=ttk.Spinbox(row,textvariable=var,from_=low,to=high,increment=step,width=12)
            box.pack(side='left');self.inputs[key]=box
            ttk.Label(row,text=f'{low:g}–{high:g}',style='Hint.TLabel').pack(side='left',padx=12)
        ttk.Label(body,text='概率只在驾驶器确认快速收油时判断一次；冷却从允许的上一组起点计算。\n连发次数受四声部池约束，包含仍在衰减的尾音；排队成功不保证声部启动。\n单次试听绕过自动触发概率与冷却。缺少音色参数的类型仍不发声。',
            style='Hint.TLabel',wraplength=590).pack(anchor='w',pady=(12,6))
        self.message=tk.StringVar(value='默认设置保持原调度行为；配方随参数和行程保存。')
        ttk.Label(body,textvariable=self.message,style='Hint.TLabel',wraplength=590).pack(fill='x',pady=10)
        row=ttk.Frame(body);row.pack(fill='x',pady=5)
        ttk.Button(row,text='恢复默认',command=self.defaults).pack(side='left')
        self.apply_button=ttk.Button(row,text='应用到下次播放',style='Primary.TButton',command=self.apply)
        self.apply_button.pack(side='right');ttk.Button(row,text='取消',command=self.close).pack(side='right',padx=8)

    def defaults(self):
        for key,value in self.owner.bridge.event_policy_defaults.items():self.vars[key].set(f'{value:g}')

    def apply(self):
        if self.owner.running():self.message.set('请先停止监听，再应用事件触发配方。');return
        try:
            configuration=policy.validate({key:float(var.get()) for key,var in self.vars.items()})
            self.owner.event_policy=deepcopy(configuration)
            self.owner.message.set('触发配方已应用到下次监听／完整流程；随参数和行程保存。')
            self.close()
        except (ValueError,TypeError) as error:self.message.set(str(error))

    def close(self):
        self.owner.policy_panel=None;self.root.destroy()
