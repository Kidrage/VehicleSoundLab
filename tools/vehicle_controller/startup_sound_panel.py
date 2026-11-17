"""Two convenient views of the same event controls, not a second sound path."""
import tkinter as tk
from tkinter import ttk

class StartupSoundPanel:
    def __init__(self,window,parent):
        self.window=window;self.inputs=[];self.rows=[];self.locked=False
        box=ttk.LabelFrame(parent,text='启动声音',padding=10);box.pack(fill='x',pady=(10,0))
        enabled=ttk.Checkbutton(box,text='启用独立事件（含启动）',variable=window.event_panel.enabled)
        enabled.pack(anchor='w',pady=(0,6));self.inputs.append(enabled)
        for kind,label in ((1,'拖转'),(2,'接火')):
            row=ttk.Frame(box);row.pack(fill='x',pady=4);ttk.Label(row,text=label,width=5).pack(side='left')
            var=window.vars['event_level_'+str(kind)];read=tk.StringVar()
            scale=ttk.Scale(row,variable=var,from_=0,to=2);scale.pack(side='left',fill='x',expand=True,padx=4)
            ttk.Label(row,textvariable=read,width=5,anchor='e').pack(side='right');self.inputs.append(scale)
            self.rows.append((kind,var,read,scale))
        self.status=tk.StringVar();ttk.Label(box,textvariable=self.status,style='Hint.TLabel',wraplength=250).pack(anchor='w',pady=(5,0))

    def lock(self,active):
        self.locked=active;self.refresh()

    def refresh(self):
        mask=self.window.event_panel.available_mask()
        self.inputs[0].state(['disabled'] if self.locked else ['!disabled'])
        for kind,var,text,widget in self.rows:
            try:text.set(f'{var.get()*100:.0f}%')
            except tk.TclError:pass
            widget.state(['disabled'] if self.locked or not mask&(1<<kind) else ['!disabled'])
        self.status.set('拖转 → 接火 → 同一 DNA 怠速\n总电平在“独立事件”页调整。' if self.window.event_panel.enabled.get() else
                        '当前配方关闭独立事件；勾选后启动声才会发出。')
