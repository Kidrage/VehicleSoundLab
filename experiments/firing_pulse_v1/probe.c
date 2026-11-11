#define _CRT_SECURE_NO_WARNINGS
#include "adapter.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "spatial/scene.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
static uint64_t source_state(const VslEngine *e,VslEngine *copy) {
    const unsigned char *p;size_t i;uint64_t h=VSL_TAKE_HASH_INITIAL;
    memcpy(copy,e,sizeof *copy);memset(&copy->acoustics,0,sizeof copy->acoustics);
    memset(&copy->spatial,0,sizeof copy->spatial);memset(&copy->objects,0,sizeof copy->objects);copy->peak=0;
    p=(const unsigned char *)copy;for(i=0;i<sizeof *copy;++i) { h^=p[i];h*=UINT64_C(1099511628211); }return h;
}
static int kernel_probe(const char *path,unsigned rate) {
    FpKernel s;VslWavWriter w={0};float data[2];unsigned i;int ok=0;
    if(!fp_kernel_init(&s,rate)||!vsl_wav_begin_float(&w,path,rate,2))return 1;
    fp_kernel_strike(&s,0,.37/rate,1,.000075,.000028);
    for(i=0;i<rate/50;++i) {
        double y[2];fp_kernel_tick(&s,y);data[0]=(float)y[0];data[1]=(float)y[1];
        if(!vsl_wav_write(&w,data,1))goto done;
    }
    ok=1;
done:ok=vsl_wav_end(&w)&&ok;return ok?0:2;
}
int main(int argc,char **argv) {
    VslTake t={0};VslTakePlayer player;VslEngine *e=NULL,*copy=NULL;FpAdapter s;
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0};FILE *trace=NULL,*state=NULL,*meta=NULL;
    char path[4096],*end;int mode,channels,c,ok=0;unsigned n,i;
    float output[257*12],sources[257*VSL_OBJECTS],mono[257];
    if(argc==4&&!strcmp(argv[1],"--kernel"))return kernel_probe(argv[2],(unsigned)strtoul(argv[3],NULL,10));
    if(argc!=5||strlen(argv[2])>3800)return 1;
    mode=(int)strtol(argv[3],&end,10);if(end==argv[3]||*end||mode<0||mode>2)return 1;
    channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||(channels!=2&&channels!=12))return 1;
    e=malloc(sizeof *e);copy=malloc(sizeof *copy);
    if(!e||!copy||!vsl_take_load(argv[1],&t)||!vsl_take_player_init(&player,e,&t)||!fp_init(&s,t.sample_rate,mode))goto done;
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,t.sample_rate,channels))goto done;
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,t.sample_rate,1))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    snprintf(path,sizeof path,"%s_state.csv",argv[2]);state=vsl_fopen(path,"w");if(!state)goto done;
    fputs("frame,native_source_state_fnv1a64,events_l,events_r\n",state);ok=1;
    while((n=fp_take(&player,e,&s,output,257,channels,sources))!=0) {
        if(!vsl_wav_write(&mix,output,n))ok=0;
        for(i=0;i<n*(unsigned)channels;++i)if(!isfinite(output[i])||fabs(output[i])>=.95)ok=0;
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)t.sample_rate);
        fprintf(state,"%" PRIu64 ",%016" PRIx64 ",%" PRIu64 ",%" PRIu64 "\n",
            e->frame,source_state(e,copy),s.accepted[0],s.accepted[1]);
        if(!ok)break;
    }
    if(e->frame!=t.frames||(!mode&&channels==2&&player.audio_hash!=t.audio_hash)||s.kernel.overflow||s.denied)ok=0;
    snprintf(path,sizeof path,"%s_meta.json",argv[2]);meta=vsl_fopen(path,"w");if(!meta) { ok=0;goto done; }
    fprintf(meta,"{\"experiment\":\"firing_pulse_v1\",\"base_runtime\":\"%s\",\"mode\":%d,\"frames\":%" PRIu64 ",\"channels\":%d,\"events_l\":%" PRIu64 ",\"events_r\":%" PRIu64 ",\"denied\":%" PRIu64 ",\"overflow\":%u,\"max_delta\":%.17g,\"audio_hash\":\"%016" PRIx64 "\"}",
        VSL_VERSION,mode,e->frame,channels,s.accepted[0],s.accepted[1],s.denied,s.kernel.overflow,s.max_delta,player.audio_hash);
    printf("firing_pulse_v1 | mode%d | frames%" PRIu64 " | %s\n",mode,e->frame,ok?"pass":"FAIL");
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(state) { if(ferror(state))ok=0;if(fclose(state))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    vsl_take_free(&t);free(e);free(copy);return ok?0:2;
}
