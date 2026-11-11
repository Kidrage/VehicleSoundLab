#define _CRT_SECURE_NO_WARNINGS
#include "response.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "spatial/scene.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <inttypes.h>
static int impulse(const char *path,double coordinate,int structure) {
    const VslCharacterProfile *p=vsl_character_profile();VslResponseKernel base,candidate;
    const VslCharacterMode *m=structure?p->structure:p->pressure;
    unsigned count=structure?VSL_CHARACTER_STRUCTURE_MODES:VSL_CHARACTER_PRESSURE_MODES;
    double weights[VSL_RESPONSE_MAX_MODES];VslWavWriter w={0};float pair[2];unsigned i;int ok=1;
    vsl_response_kernel_init(&base,m,count,192000);vsl_response_kernel_init(&candidate,m,count,192000);
    for(i=0;i<count;++i)weights[i]=m[i].weight;
    vsl_response_kernel_strike(&base,weights,1,0,0);vsl_response_kernel_strike(&candidate,weights,1,coordinate,0);
    if(!vsl_wav_begin_float(&w,path,192000,2))return 2;
    for(i=0;i<192000/2;++i) {
        pair[0]=(float)vsl_response_kernel_read(&base);pair[1]=(float)vsl_response_kernel_read(&candidate);
        if(!vsl_wav_write(&w,pair,1)) { ok=0;break; }
        vsl_response_kernel_advance(&base);vsl_response_kernel_advance(&candidate);
    }
    ok=vsl_wav_end(&w)&&ok;return ok?0:2;
}
static uint64_t state_hash(const VslEngine *e,VslEngine *copy) {
    const unsigned char *p;size_t i;uint64_t h=VSL_TAKE_HASH_INITIAL;
    memcpy(copy,e,sizeof *copy);memset(&copy->acoustics,0,sizeof copy->acoustics);
    memset(&copy->spatial,0,sizeof copy->spatial);memset(&copy->objects,0,sizeof copy->objects);copy->peak=0;
    p=(const unsigned char *)copy;for(i=0;i<sizeof *copy;++i) { h^=p[i];h*=UINT64_C(1099511628211); }return h;
}
int main(int argc,char **argv) {
    VslTake t={0};VslTakePlayer player;VslEngine *e=NULL,*copy=NULL;VslResponseShape response;
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0};FILE *trace=NULL,*state=NULL,*meta=NULL;
    char path[4096],*end;double amount;int channels,c,ok=0;unsigned n,i;
    float output[257*12],sources[257*VSL_OBJECTS],mono[257];
    if(argc!=5||strlen(argv[2])>3800)return 1;
    if(!strcmp(argv[1],"impulse")) {
        amount=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(amount)||amount<-1||amount>1)return 1;
        channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||channels<0||channels>1)return 1;
        return impulse(argv[2],amount,channels);
    }
    amount=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||(channels!=2&&channels!=12))return 1;
    e=malloc(sizeof *e);copy=malloc(sizeof *copy);
    if(!e||!copy||!vsl_take_load(argv[1],&t)||!vsl_take_player_init(&player,e,&t))goto done;
    vsl_response_init(&response,t.sample_rate,amount);
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,t.sample_rate,channels))goto done;
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,t.sample_rate,1))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    snprintf(path,sizeof path,"%s_state.csv",argv[2]);state=vsl_fopen(path,"w");if(!state)goto done;
    fputs("frame,native_state_fnv1a64,pressure_events,structure_events,shape_min,shape_max\n",state);ok=1;
    while((n=vsl_response_take(&player,e,&response,output,257,channels,sources))!=0) {
        if(!vsl_wav_write(&mix,output,n))ok=0;
        for(i=0;i<n*(unsigned)channels;++i)if(!isfinite(output[i])||fabs(output[i])>=.95)ok=0;
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)t.sample_rate);
        fprintf(state,"%" PRIu64 ",%016" PRIx64 ",%" PRIu64 ",%" PRIu64 ",%.17g,%.17g\n",
            e->frame,state_hash(e,copy),response.pressure_events,response.structure_events,response.coordinate_min,response.coordinate_max);
        if(!ok)break;
    }
    if(e->frame!=t.frames||(!amount&&channels==2&&player.audio_hash!=t.audio_hash))ok=0;
    snprintf(path,sizeof path,"%s_meta.json",argv[2]);meta=vsl_fopen(path,"w");if(!meta) { ok=0;goto done; }
    fprintf(meta,"{\"experiment\":\"response_shape_v1\",\"base_runtime\":\"%s\",\"amount\":%.17g,\"frames\":%" PRIu64 ",\"channels\":%d,\"pressure_events\":%" PRIu64 ",\"structure_events\":%" PRIu64 ",\"coordinate_min\":%.17g,\"coordinate_max\":%.17g,\"audio_hash\":\"%016" PRIx64 "\",\"native_take_hash\":\"%016" PRIx64 "\"}",
        VSL_VERSION,amount,e->frame,channels,response.pressure_events,response.structure_events,response.coordinate_min,response.coordinate_max,player.audio_hash,t.audio_hash);
    printf("response_shape_v1 | base %s | amount %.3f | channels %d | frames %" PRIu64 " | pressure %" PRIu64 " | structure %" PRIu64 " | %s\n",
        VSL_VERSION,amount,channels,e->frame,response.pressure_events,response.structure_events,ok?"pass":"FAIL");
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(state) { if(ferror(state))ok=0;if(fclose(state))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    vsl_take_free(&t);free(e);free(copy);return ok?0:2;
}
