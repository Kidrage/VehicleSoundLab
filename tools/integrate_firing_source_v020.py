"""One-time explicit integration; preserve all frozen releases/experiments."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
files={}
def change(name,old,new):
    text=files.get(name,(ROOT/name).read_text(encoding='utf-8'))
    if text.count(old)!=1: raise ValueError((name,old[:100],text.count(old)))
    files[name]=text.replace(old,new)
def main():
    if (ROOT/'src/core/pulse_kernel.c').exists(): raise SystemExit('Integration already started/completed.')
    for suffix in ['c','h']:
        text=(ROOT/f'experiments/firing_pulse_v1/kernel.{suffix}').read_text(encoding='utf-8')
        for a,b in [('VSL_FIRING_PULSE_KERNEL_H','VSL_PULSE_KERNEL_H'),('"kernel.h"','"pulse_kernel.h"'),('"profile.h"','"profiles/firing_source.h"'),('FP_OVERSAMPLE','VSL_PULSE_OVERSAMPLE'),('FP_TAPS','VSL_PULSE_TAPS'),('FP_VOICES','VSL_PULSE_VOICES'),('FpVoice','VslPulseVoice'),('FpKernel','VslPulseKernel'),('fp_','vsl_pulse_')]: text=text.replace(a,b)
        files[f'src/core/pulse_kernel.{suffix}']=text
    change('CMakeLists.txt','VERSION 0.19.1','VERSION 0.20.0')
    change('CMakeLists.txt','  src/core/event_split.c','  src/core/pulse_kernel.c src/core/firing_source.c src/profiles/firing_source.c\n  src/core/event_split.c')
    change('src/core/types.h','#define VSL_VERSION "0.19.0"','#include "firing_source_types.h"\n#define VSL_VERSION "0.20.0"')
    change('src/core/types.h','double pressure_texture,structure_transfer,response_shape,event_color;','double pressure_texture,structure_transfer,response_shape,event_color;\n    int firing_source;\n    double pulse_amount;')
    change('src/core/types.h','    VslEventColor color;','    VslEventColor color;\n    VslFiringSource firing_source;')
    change('src/core/engine.c','#include "event_color.h"','#include "event_color.h"\n#include "firing_source.h"')
    change('src/core/engine.c','    vsl_character_init(e,e->nvh.seed);','    vsl_character_init(e,e->nvh.seed);\n    vsl_firing_source_init(&e->firing_source,e->sample_rate);')
    change('src/core/engine.c','UNIT(event_color);','UNIT(event_color);UNIT(pulse_amount);')
    change('src/core/engine.c','    e->target.propagation=p->propagation?1:0;','    e->target.propagation=p->propagation?1:0;\n    e->target.firing_source=(int)vsl_clamp(p->firing_source,VSL_SOURCE_OSC,VSL_SOURCE_VARIABLE);')
    change('src/core/engine.c','FOLLOW(event_color);','FOLLOW(event_color);FOLLOW(pulse_amount);')
    change('src/core/engine.c','        ir=vsl_ir_tick','        vsl_firing_source_tick(&e->firing_source,e,o,main_pressure);\n        ir=vsl_ir_tick')
    change('src/core/profiles.c','    p.event_color=0;','    p.firing_source=VSL_SOURCE_OSC;p.pulse_amount=1; /* Explicit opt-in; original voice at mode0. */\n    p.event_color=0;')
    change('src/session/parameters.h','D(response_shape) D(event_color)','D(response_shape) D(event_color) I(firing_source) D(pulse_amount)')
    change('src/session/parameters.c','            else if(!strcmp(f[i].name,"gear"))hi=7;','            else if(!strcmp(f[i].name,"gear"))hi=7;\n            else if(!strcmp(f[i].name,"firing_source"))hi=VSL_SOURCE_VARIABLE;')
    change('src/app/preset.c','D(response_shape),D(event_color)}','D(response_shape),D(event_color),I(firing_source),D(pulse_amount)}')
    change('src/io/take_file.c','VSLTAKE 4','VSLTAKE 5')
    change('src/io/take_file.c','word(f,"4")','word(f,"5")')
    change('src/io/scene_metadata.c','FIELD(event_color);','FIELD(event_color);FIELD(firing_source);FIELD(pulse_amount);')
    change('src/io/drive_trace.c','event_color_max_mod",f);','event_color_max_mod,firing_source_target,pulse_amount_target,pulse_mix,pulse_variation,pulse_events_l,pulse_events_r,pulse_overflow",f);')
    change('src/io/drive_trace.c','(unsigned long long)e->color.events[0],(unsigned long long)e->color.events[1],e->color.max_mod);', '(unsigned long long)e->color.events[0],(unsigned long long)e->color.events[1],e->color.max_mod);\n    fprintf(f,",%d,%.12g,%.12g,%.12g,%llu,%llu,%u",e->target.firing_source,e->target.pulse_amount,e->firing_source.mix,e->firing_source.variation,\n        (unsigned long long)e->firing_source.accepted[0],(unsigned long long)e->firing_source.accepted[1],e->firing_source.kernel.overflow);')
    change('build.ps1',"'build-app0191'","'build-v020'")
    for name,text in files.items():(ROOT/name).write_text(text,encoding='utf-8')
    print('DSP020 integrated. UI and verification still required.')
if __name__=='__main__': main()
