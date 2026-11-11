#include "render_session.h"
#include "wav.h"
#include "file.h"
#include "drive/drive.h"
#include "spatial/scene.h"
#include "drive/scenarios.h"
#include "drive_trace.h"
#include <stdlib.h>
#include <math.h>
#include <string.h>
int vsl_render_file(const char*path,const VslParams*p,double seconds,int drive,const char*dna,const char*ir) {
    return vsl_render_session(path,p,seconds,drive,dna,ir,2,NULL,NULL);
}
int vsl_render_session(const char*path,const VslParams*p,double seconds,int drive,const char*dna,const char*ir,
    int channels,const char*trace_path,const char*stem_prefix) {
    VslEngine*e=(VslEngine*)malloc(sizeof *e); VslWavWriter w;
    VslWavWriter stems[VSL_OBJECTS]={0};FILE*trace=NULL;
    unsigned frame,total,n;float buffer[256*12],objects[256*VSL_OBJECTS],mono[256];int ok=1,c;
    VslLifecycle last_life=VSL_OFF;VslOperating last_op=VSL_IDLE;int last_shifting=0;
    VslFuelMode last_fuel=VSL_FUEL_OFF;
    if(!e || !isfinite(seconds) || seconds<=0 || seconds>3600 || drive<0 || drive>=VSL_SCENARIO_COUNT || (channels!=2&&channels!=12)) { free(e); return 0; }
    if(seconds*48000*channels*(channels==12?4:2)>4294967167.) { free(e);return 0; }
    total=(unsigned)(seconds*48000);
    vsl_init(e,48000,48271); vsl_set_params(e,p);
    if(dna && *dna && !vsl_load_dna(e,dna)) { free(e); return 0; }
    if(ir && *ir) {
        unsigned count,sr,i; float*data=vsl_wav_read(ir,&count,&sr);
        if(!data || count>VSL_MAX_IR || sr!=48000) { free(data); free(e); return 0; }
        for(i=0;i<count;++i)data[i]=.5f*(data[2*i]+data[2*i+1]);
        ok=vsl_set_ir(e,data,count,sr); free(data);
        if(!ok) { free(e); return 0; }
    }
    if(!(channels==12?vsl_wav_begin_float(&w,path,48000,12):vsl_wav_begin_layout(&w,path,48000,2))) { free(e); return 0; }
    if(trace_path && *trace_path) {
        trace=vsl_fopen(trace_path,"w");if(!trace) { ok=0;goto done; }
        vsl_trace_header(trace);
    }
    if(stem_prefix && *stem_prefix)for(c=0;c<VSL_OBJECTS;++c) {
        char name[4096];snprintf(name,sizeof name,"%s_%s.wav",stem_prefix,vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],name,48000,1)) { ok=0;goto done; }
    }
    for(frame=0;frame<total;frame+=n) {
        VslParams current=*p;
        /* Diagnostic scenario edges align with the 200 Hz control clock. */
        unsigned chunk=drive>VSL_SCENARIO_AUTO?240:256;
        n=total-frame; if(n>chunk)n=chunk;
        vsl_scenario_apply(drive,frame/48000.,&current);
        vsl_set_params(e,&current);vsl_process_layout(e,buffer,n,channels,stem_prefix?objects:NULL);
        if(trace && (frame%4800<n || e->drive.lifecycle!=VSL_RUNNING || e->drive.shifting || last_shifting || e->drive.lifecycle!=last_life || e->drive.operating!=last_op || e->drive.fuel.mode!=last_fuel)) {
            vsl_trace_frame(trace,e,(frame+n)/48000.);
            last_life=e->drive.lifecycle;last_op=e->drive.operating;
            last_fuel=e->drive.fuel.mode;
        }
        last_shifting=e->drive.shifting;
        /* Export endpoint fades avoid clicks without altering the live DSP. */
        { unsigned i; for(i=0;i<n;++i) {
            double remain=(total-frame-i)/48000.; double fade=remain<.025?remain/.025:1;
            for(c=0;c<channels;++c)buffer[channels*i+c]*=(float)fade;
        }}
        if(!vsl_wav_write(&w,buffer,n)) { ok=0; break; }
        if(stem_prefix && *stem_prefix)for(c=0;c<VSL_OBJECTS;++c) {
            unsigned i;for(i=0;i<n;++i)mono[i]=objects[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
    }
done:
    if(trace) { if(ferror(trace))ok=0;fclose(trace); }
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    ok=vsl_wav_end(&w)&&ok; free(e); return ok;
}
