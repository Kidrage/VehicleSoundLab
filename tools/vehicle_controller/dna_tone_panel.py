"""The two DNA roles and their state response, within the primary app."""
import tkinter as tk
from tkinter import ttk
from . import dna_character as dna

class DnaTonePanel:
    def __init__(self,parent):
        self.fields={};self.inputs=[];self.labels={};self.status=tk.StringVar()
        left=ttk.Frame(parent);left.pack(side='left',fill='both',expand=True,padx=(0,20))
        right=ttk.Frame(parent);right.pack(side='left',fill='both',expand=True)
        ttk.Label(left,text='DNA = 声线 + 空气纹理',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w',pady=(6,14))
        for key,label,low,high in dna.FIELDS:
            row=ttk.Frame(left);row.pack(fill='x',pady=8)
            ttk.Label(row,text=label,width=19).pack(side='left');var=tk.DoubleVar(value=dna.defaults()[key]);self.fields[key]=var
            scale=ttk.Scale(row,variable=var,from_=low,to=high);scale.pack(side='left',fill='x',expand=True,padx=6);self.inputs.append(scale)
            read=tk.StringVar();self.labels[key]=read;ttk.Label(row,textvariable=read,width=6).pack(side='right')
        ttk.Label(left,text='声线：持续有音高的主体与发动机身份。\n纹理：细谱空气感及已配置的连续细节。\n两者属于同一 DNA，低频轰鸣另调。',style='Hint.TLabel',wraplength=400).pack(anchor='w',pady=14)
        ttk.Label(right,text='工况响应 · 倍率',font=('Microsoft YaHei UI',12,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',pady=(6,14))
        for col,text in enumerate(('工况','声线','纹理')):ttk.Label(right,text=text).grid(row=1,column=col,padx=7,pady=6)
        for key in ('line_state','air_state'):self.fields[key]=[]
        for i,state in enumerate(dna.STATES):
            ttk.Label(right,text=state).grid(row=i+2,column=0,sticky='w',padx=7,pady=8)
            for j,key in enumerate(('line_state','air_state')):
                var=tk.DoubleVar(value=1.);self.fields[key].append(var)
                entry=ttk.Spinbox(right,from_=0,to=2,increment=.05,width=7,textvariable=var)
                entry.grid(row=i+2,column=j+1,padx=7);self.inputs.append(entry)
        restore=ttk.Button(right,text='恢复 DNA 配方',command=lambda:self.load(dna.defaults()))
        restore.grid(row=8,column=0,columnspan=3,sticky='w',pady=12);self.inputs.append(restore)
        ttk.Label(right,textvariable=self.status,style='Hint.TLabel',wraplength=380).grid(row=9,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Label(right,text='先以 100% / 100% 为基准，单独关闭一层听它的作用。\n再调自然起伏，最后微调各工况倍率。',style='Hint.TLabel',wraplength=380).grid(row=10,column=0,columnspan=3,sticky='w',pady=8)

    def load(self,value):
        value=dna.validate(value)
        for key,variables in self.fields.items():
            if isinstance(variables,list):
                for var,x in zip(variables,value[key]):var.set(x)
            else:variables.set(value[key])

    def get(self):
        return dna.validate({key:[x.get() for x in variables] if isinstance(variables,list) else variables.get()
                             for key,variables in self.fields.items()})

    def lock(self,active):
        for widget in self.inputs:widget.state(['disabled'] if active else ['!disabled'])

    def refresh(self,features):
        for key,text in self.labels.items():
            try:text.set(f'{self.fields[key].get()*100:.0f}%')
            except tk.TclError:pass
        self.status.set('细谱指纹已配置：全工况共享；高转为工程延伸，可调。' if features&64 else
                        '此配方未配置细谱指纹。声线增益仍有效；纹理只调已有细节源，空槽保持静音。')
