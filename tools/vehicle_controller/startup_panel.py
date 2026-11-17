"""Separate startup editor over the native engine's nine response parameters."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk
from . import startup


class StartupPanel:
    def __init__(self,owner):
        self.owner=owner
        self.root=tk.Toplevel(owner.root);self.root.title('启动与停机响应')
        self.root.geometry('590x530' if owner.features&128 else '590x625');self.root.resizable(False,False);self.root.transient(owner.root)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        body=ttk.Frame(self.root,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text='启动与停机响应',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        flare=bool(owner.features&128)
        ttk.Label(body,text='变调接火 → 回落怠速；停止监听后应用。\n接火总时长控制变调节奏；冲转 RPM 控制主 DNA 的回落。' if flare else
            '拖转 → 接火冲转 → 回落怠速；停止监听后应用。',
            style='Hint.TLabel',wraplength=540).pack(anchor='w',pady=(8,12))
        self.vars={};self.inputs={}
        for key,label,low,high in startup.FIELDS:
            if not owner.bridge.tuning_headroom:high=round(high/1.3,8)
            var=tk.StringVar(value=f'{owner.startup_response[key]:g}');self.vars[key]=var
            if flare and key.startswith('crank_'):continue
            row=ttk.Frame(body);row.pack(fill='x',pady=4)
            ttk.Label(row,text=label,width=25).pack(side='left')
            box=ttk.Spinbox(row,textvariable=var,from_=low,to=high,
                increment=10 if key.endswith('rpm') else .005,width=12)
            box.pack(side='left');self.inputs[key]=box
            ttk.Label(row,text=f'{low:g}–{high:g}',style='Hint.TLabel').pack(side='left',padx=12)
        self.message=tk.StringVar(value=f"默认冲转峰值 {owner.bridge.startup_defaults['flare_rpm']:g} RPM。")
        ttk.Label(body,textvariable=self.message,style='Hint.TLabel',wraplength=540).pack(fill='x',pady=10)
        row=ttk.Frame(body);row.pack(fill='x',pady=4)
        self.default_button=ttk.Button(row,text='恢复原默认',command=self.defaults);self.default_button.pack(side='left')
        row=ttk.Frame(body);row.pack(fill='x',pady=5)
        self.apply_button=ttk.Button(row,text='应用到下次播放',style='Primary.TButton',command=self.apply);self.apply_button.pack(side='right')
        ttk.Button(row,text='取消',command=self.close).pack(side='right',padx=8)

    def defaults(self):
        for key,value in self.owner.bridge.startup_defaults.items():self.vars[key].set(f'{value:g}')

    def apply(self):
        if self.owner.running():self.message.set('请先停止监听，再应用启动响应。');return
        try:
            response=startup.validate({key:float(var.get()) for key,var in self.vars.items()})
            self.owner.startup_response=deepcopy(response)
            self.owner.message.set('启动响应已应用；点击启动或完整流程试听。参数会随配方和行程保存。')
            self.close()
        except (ValueError,TypeError) as error:self.message.set(str(error))

    def close(self):
        self.owner.startup_panel=None;self.root.destroy()
