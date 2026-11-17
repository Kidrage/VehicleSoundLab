"""Stopped-only state-bank editor; synthesis and state selection remain in C."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk,filedialog
from . import dna_bank as dna,take

STATE_LABELS={'base':'默认／巡航','idle':'怠速','power':'给油／加速','overrun':'收油／切断'}


class DnaPanel:
    def __init__(self,owner):
        self.owner=owner;bank=owner.dna_bank or {}
        self.groups={'base':deepcopy(bank.get('anchors',[])),**deepcopy(bank.get('states',{}))}
        self.root=tk.Toplevel(owner.root);self.root.title('工作台DNA → 驾驶声源')
        self.root.geometry('780x740');self.root.minsize(720,700);self.root.transient(owner.root)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        body=ttk.Frame(self.root,padding=20);body.pack(fill='both',expand=True)
        ttk.Label(body,text='工作台DNA → 驾驶声源',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        ttk.Label(body,text='每组可导入1–8个同分音数锚点。驾驶器选择状态，同一OSC时钟平滑变换声纹。\n缺少怠速／给油／收油组时采用默认组；可选声层和独立事件仍分别配置。',
            wraplength=720,style='Hint.TLabel').pack(anchor='w',pady=(8,12))
        row=ttk.Frame(body);row.pack(fill='x',pady=(0,8))
        ttk.Label(row,text='当前编辑').pack(side='left',padx=(0,10))
        self.state=tk.StringVar(value=STATE_LABELS['base'])
        self.state_box=ttk.Combobox(row,textvariable=self.state,values=list(STATE_LABELS.values()),state='readonly',width=20)
        self.state_box.pack(side='left');self.state_box.bind('<<ComboboxSelected>>',lambda _:self.refresh())
        self.summary=tk.StringVar();ttk.Label(row,textvariable=self.summary,style='Hint.TLabel').pack(side='right')
        self.list=ttk.Treeview(body,columns=('hz','harmonics','components'),show='tree headings',height=6)
        self.list.heading('#0',text='声纹锚点');self.list.column('#0',width=300)
        for key,label in (('hz','基频 Hz'),('harmonics','分音'),('components','联动')):
            self.list.heading(key,text=label);self.list.column(key,width=100,anchor='e')
        self.list.pack(fill='both',expand=True)
        row=ttk.Frame(body);row.pack(fill='x',pady=10)
        ttk.Button(row,text='导入 DNA 包／模型…',command=self.import_file).pack(side='left')
        ttk.Button(row,text='移除选中',command=self.remove).pack(side='left',padx=8)
        ttk.Button(row,text='清空当前组',command=self.clear).pack(side='left')
        self.vars={}
        defaults=dict(name=bank.get('name','自定义驾驶DNA'),reference_rpm=(self.groups['base'][0]['base_hz']/bank['root_per_rpm'] if bank else 3000),
            seed=bank.get('seed',48271),align_orders=bank.get('align_orders',12),detail=bank.get('detail',1.),
            transition_seconds=bank.get('transition_seconds',.12))
        for key,label in (('name','音色名称'),('reference_rpm','默认首锚点参考 RPM'),('detail','DNA细节 · 0–1.3'),
                          ('transition_seconds','状态过渡时间 · 0.02–2.6 s'),('align_orders','相位对齐 · 0–32'),('seed','随机种子')):
            row=ttk.Frame(body);row.pack(fill='x',pady=3);ttk.Label(row,text=label,width=25).pack(side='left')
            self.vars[key]=tk.StringVar(value=str(defaults[key]));ttk.Entry(row,textvariable=self.vars[key]).pack(side='left',fill='x',expand=True)
        ttk.Label(body,text='参考RPM为人工工程映射，四组共用；不同录音必须先确认阶次与视角可比。\n过渡时间是63%响应时间，约3倍达到95%；范围外变调会在驾驶窗口提示。\n单状态包导入当前组，多状态包整体替换。不会自动截断高频来兼容分音数。',
            style='Hint.TLabel',wraplength=720).pack(anchor='w',pady=10)
        self.message=tk.StringVar();ttk.Label(body,textvariable=self.message,style='Hint.TLabel',wraplength=720).pack(fill='x')
        row=ttk.Frame(body);row.pack(fill='x',pady=(12,0))
        ttk.Button(row,text='恢复目录声源',command=self.catalog).pack(side='left')
        ttk.Button(row,text='导出DNA包…',command=self.export).pack(side='left',padx=8)
        ttk.Button(row,text='应用到驾驶器',style='Primary.TButton',command=self.apply).pack(side='right')
        self.refresh()

    def selected(self):
        return next(key for key,label in STATE_LABELS.items() if label==self.state.get())

    @property
    def anchors(self):return self.groups.get(self.selected(),[])

    def refresh(self):
        self.list.delete(*self.list.get_children())
        for i,row in enumerate(self.anchors):self.list.insert('', 'end',iid=str(i),text=row['name'],values=(f"{row['base_hz']:.3f}",row['harmonics'],row['components']))
        self.summary.set('  /  '.join(f'{label.split("／")[0]} {len(self.groups.get(key,[]))}' for key,label in STATE_LABELS.items()))

    def configuration(self,groups=None):
        groups=self.groups if groups is None else groups
        base=dna.create(groups['base'],float(self.vars['reference_rpm'].get()),self.vars['name'].get(),
            int(self.vars['seed'].get()),int(self.vars['align_orders'].get()),float(self.vars['detail'].get()))
        return dna.with_states(base,{key:groups[key] for key in dna.STATES if groups.get(key)},float(self.vars['transition_seconds'].get()))

    def import_file(self,path=None):
        if path is None:path=filedialog.askopenfilename(parent=self.root,title='导入工作台DNA',filetypes=[('DNA模型／参数包','*.model *.json')])
        if not path:return
        try:
            imported=dna.read(path)
            if imported is None:raise ValueError('文件没有DNA参数包')
            selected=self.selected();groups=deepcopy(self.groups)
            if imported.get('schema')==dna.STATE_SCHEMA:
                proposal=imported
            else:
                groups[selected]=deepcopy(imported['anchors']) if imported.get('schema')==dna.SCHEMA else sorted(self.anchors+[imported],key=lambda x:x['base_hz'])
                if imported.get('schema')==dna.SCHEMA and selected=='base':
                    proposal=dna.with_states(imported,{key:groups[key] for key in dna.STATES if groups.get(key)},float(self.vars['transition_seconds'].get()))
                else:proposal=self.configuration(groups)
            # Validate every group before adopting any editor field.
            proposal=dna.supported(proposal,self.owner.bridge.abi())
            self.groups={'base':deepcopy(proposal['anchors']),**deepcopy(proposal.get('states',{}))}
            for key in ('name','seed','align_orders','detail'):self.vars[key].set(str(proposal[key]))
            self.vars['reference_rpm'].set(str(self.groups['base'][0]['base_hz']/proposal['root_per_rpm']))
            if proposal.get('states'):self.vars['transition_seconds'].set(str(proposal['transition_seconds']))
            self.refresh();self.message.set('已导入参数；应用后生效。状态组沿用默认组的RPM映射。')
        except Exception as error:self.message.set(str(error))

    def remove(self):
        selected={int(i) for i in self.list.selection()}
        self.groups[self.selected()]=[row for i,row in enumerate(self.anchors) if i not in selected];self.refresh()

    def clear(self):
        self.groups[self.selected()]=[];self.refresh()
        self.message.set('默认组必须有锚点才能应用。' if self.selected()=='base' else '该状态将使用默认组。')

    def export(self):
        try:
            bank=self.configuration();path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.dnabank.json',title='导出驾驶DNA包')
            if path:take.save(path,bank);self.message.set('完整状态参数包已保存；不含录音。')
        except Exception as error:self.message.set(str(error))

    def apply(self):
        try:self.owner.apply_dna(self.configuration());self.close()
        except Exception as error:self.message.set(str(error))

    def catalog(self):
        try:self.owner.apply_dna(None);self.close()
        except Exception as error:self.message.set(str(error))

    def close(self):
        self.owner.dna_panel=None;self.root.destroy()
