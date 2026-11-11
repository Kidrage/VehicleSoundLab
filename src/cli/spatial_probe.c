#define _CRT_SECURE_NO_WARNINGS
#include "core/engine.h"
#include "spatial/scene.h"
#include "spatial/propagation.h"
#include "profiles/propagation.h"
#include "io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
int main(int argc,char **argv) {
    VslEngine *e;VslPropagation *s;const VslPropagationProfile *p=vsl_propagation_profile();
    const VslObjectInfo *o=vsl_object_info(VSL_EXHAUST_L);
    double sr=argc>2?atof(argv[2]):48000,fraction=argc>3?atof(argv[3]):-1;
    char path[4096];FILE *f;int n,i,ok=1;
    if(argc<2||!isfinite(sr)||sr<16000||sr>192000||fraction>1||fraction< -1)return 1;
    e=malloc(sizeof *e);if(!e)return 2;vsl_init(e,sr,48271);vsl_scene_update(e,2);s=&e->spatial.propagation;
    if(fraction>=0) {
        s->target_delay[VSL_EXHAUST_L][2]=floor(s->target_delay[VSL_EXHAUST_L][2])+fraction;
        s->delay[VSL_EXHAUST_L][2]=s->target_delay[VSL_EXHAUST_L][2];
    }
    snprintf(path,sizeof path,"%s.json",argv[1]);f=vsl_fopen(path,"w");if(!f) { free(e);return 2; }
    fprintf(f,"{\"dsp\":\"%s\",\"sample_rate\":%.12g,\"source\":[%.12g,%.12g,%.12g],\"listener\":[-3,0,0.9],\"ear_spacing_m\":%.12g,\"speed_mps\":%.12g,\"algorithmic_latency_samples\":%d,\"interpolator_taps\":%d,\"interpolator_phases\":%d,\"forced_centre_fraction\":%.12g,\"clamped_paths\":%u,\"delay_samples\":[",
        VSL_VERSION,sr,o->x,o->y,o->z,p->ear_spacing_m,p->speed_mps,VSL_PATH_LATENCY,VSL_PATH_TAPS,VSL_PATH_PHASES,fraction,s->clamped_paths);
    for(i=0;i<3;++i)fprintf(f,"%s%.17g",i?",":"",s->target_delay[VSL_EXHAUST_L][i]);
    fprintf(f,"],\"gain\":[");for(i=0;i<3;++i)fprintf(f,"%s%.17g",i?",":"",s->target_gain[VSL_EXHAUST_L][i]);
    fprintf(f,"],\"shadow\":[%.17g,%.17g],\"shadow_hz\":%.12g,\"scope\":\"C module impulse paths before final scene highpass/width/room; forced fraction is an interpolation control, not a modified car geometry\"}\n",s->target_shadow[VSL_EXHAUST_L][0],s->target_shadow[VSL_EXHAUST_L][1],p->shadow_hz);
    if(ferror(f))ok=0;if(fclose(f))ok=0;
    snprintf(path,sizeof path,"%s.csv",argv[1]);f=vsl_fopen(path,"w");if(!f) { free(e);return 2; }
    fprintf(f,"sample,left,right,centre\n");
    for(n=0;n<(int)(sr*.05);++n) {
        double out[3];vsl_propagation_tick(s,VSL_EXHAUST_L,n==0?1:0,out);vsl_propagation_advance(s);
        fprintf(f,"%d,%.17g,%.17g,%.17g\n",n,out[0],out[1],out[2]);
    }
    if(ferror(f))ok=0;if(fclose(f))ok=0;
    free(e);return ok?0:2;
}
