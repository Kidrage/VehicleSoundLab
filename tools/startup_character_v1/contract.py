import ctypes as C
class Ridge(C.Structure):
    _fields_=[('start_frame',C.c_uint),('frames',C.c_uint),('hz',C.c_double),('slew',C.c_double),('amplitude',C.c_double*2),('phase',C.c_double*2)]
def pack(rows):
    result=(Ridge*len(rows))()
    for out,row in zip(result,rows):
        out.start_frame=row['start_frame'];out.frames=row['frames'];out.hz=row['hz'];out.slew=row['slew_hz_per_second'];out.amplitude[:]=row['amplitude'];out.phase[:]=row['phase']
    return result
