"""Measured process peak and weak-reference array ownership/lifetime records."""
import ctypes
import weakref
import numpy as np


def process_memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
    api=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    api.argtypes=(ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong)
    c=Counters();c.cb=ctypes.sizeof(c)
    if not api(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):raise ctypes.WinError(ctypes.get_last_error())
    return dict(working_set_bytes=c.WorkingSetSize,cumulative_peak_working_set_bytes=c.PeakWorkingSetSize,
                private_commit_bytes=c.PagefileUsage,cumulative_peak_private_commit_bytes=c.PeakPagefileUsage)


class ArrayLedger:
    """Track actual ndarray backing stores, without extending their lifetimes.

    This excludes LAPACK/BLAS workspaces and unregistered temporaries. Process
    working set/peak are recorded separately and never equated to this subtotal.
    """
    def __init__(self):self.stores=[];self.arrays=[];self.events=[]

    def add(self,name,array):
        array=np.asarray(array);root=array
        while isinstance(root.base,np.ndarray):root=root.base
        matches=[i for i,(r,n) in enumerate(self.stores) if r() is root]
        if matches:store=matches[0]
        else:store=len(self.stores);self.stores.append((weakref.ref(root),int(root.nbytes)))
        record=dict(name=name,storage=store,shape=list(array.shape),strides=list(array.strides),
            bytes=int(array.nbytes),backing_bytes=int(root.nbytes),dtype=str(array.dtype),
            F_contiguous=bool(array.flags.f_contiguous),C_contiguous=bool(array.flags.c_contiguous),
            owns_data=bool(array.flags.owndata))
        self.arrays.append(record);self.events.append(dict(event='array',**record))
        return array

    def snapshot(self,phase):
        live=[i for i,(r,n) in enumerate(self.stores) if r() is not None]
        self.events.append(dict(event='snapshot',phase=phase,live_storages=live,
            tracked_live_backing_bytes=sum(self.stores[i][1] for i in live),**process_memory()))

    def report(self):
        return dict(events=self.events,storage_bytes=[n for r,n in self.stores],
            max_tracked_live_backing_bytes=max((e['tracked_live_backing_bytes'] for e in self.events if e['event']=='snapshot'),default=0),
            scope='Registered ndarray backing stores only; excludes unregistered/library temporaries; process peak is cumulative')
