"""One normal-startup volume, shared by native controls/takes/presets."""
import tkinter as tk
from tkinter import ttk

class StartupSoundPanel:
    def __init__(self,window,parent):
        self.window=window;self.locked=False
        box=ttk.LabelFrame(parent,text='启动声音',padding=10);box.pack(fill='x',pady=(10,0))
        row=ttk.Frame(box);row.pack(fill='x')
        ttk.Label(row,text='电平',width=5).pack(side='left')
        var=window.vars.setdefault('startup_gain',tk.DoubleVar())
        self.scale=ttk.Scale(row,variable=var,from_=0,to=2.6 if window.bridge.tuning_headroom else 1)
        self.scale.pack(side='left',fill='x',expand=True,padx=4)
        self.read=tk.StringVar();ttk.Label(row,textvariable=self.read,width=5,anchor='e').pack(side='right')
        window.widgets['startup_gain']=(self.scale,128|8)
        self.status=tk.StringVar();ttk.Label(box,textvariable=self.status,style='Hint.TLabel',wraplength=230).pack(anchor='w',pady=(6,0))

    def lock(self,active):
        self.locked=active;self.refresh()

    def refresh(self):
        w=self.window;features=getattr(w,'features',0)
        enabled=bool(features&128 or features&8 and not w.event_panel.enabled.get())
        self.scale.state(['!disabled'] if enabled and not self.locked else ['disabled'])
        headroom=bool(features&128 and features&256)
        self.scale.configure(to=2.6 if headroom else 1.3 if features&256 else 1)
        try:self.read.set(f"{w.vars['startup_gain'].get():.2f}" if headroom else f"{w.vars['startup_gain'].get()*100:.0f}%")
        except tk.TclError:pass
        duration=w.startup_response['catch_rise_seconds']+w.startup_response['catch_settle_seconds']
        self.status.set(f'变调接火 {duration:.2f} 秒 → 怠速\n'+('0.50 = 原默认音量 · 范围 0–2.60' if headroom else '点击“启动”直接试听。') if features&128 else
                        '当前音色使用原启停配方。')
