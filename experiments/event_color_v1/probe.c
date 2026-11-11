#define _CRT_SECURE_NO_WARNINGS
#include "color.h"
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
static uint64_t original_state(const VslEngine *e,VslEngine *copy) {
    const unsigned char *p;size_t i;uint64_t h=VSL_TAKE_HASH_INITIAL;
    memcpy(copy,e,sizeof *copy);memset(&copy->acoustics,0,sizeof copy->acoustics);
    memset(&copy->spatial,0,sizeof copy->spatial);memset(&copy->objects,0,sizeof copy->objects);copy->peak=0;
    p=(const unsigned char *)copy;for(i=0;i<sizeof *copy;++i) { h^=p[i];h*=UINT64_C(1099511628211); }return h;
}
int main(int argc,char **argv) {
    VslTake t={0};VslTakePlayer player;VslEngine *e=NULL,*copy=NULL;VslEventColor color={0};
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0};FILE *trace=NULL,*state=NULL,*meta=NULL,*taps=NULL;
    char path[4096],*end;double amount;int channels,c,ok=0;unsigned n,i;
    float output[257*12],sources[257*VSL_OBJECTS],mono[257];
    if((argc!=5&&argc!=6)||strlen(argv[2])>3800)return 1;
    amount=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||(channels!=2&&channels!=12))return 1;
    if(argc==6&&strcmp(argv[5],"taps"))return 1;
    e=malloc(sizeof *e);copy=malloc(sizeof *copy);
    if(!e||!copy||!vsl_take_load(argv[1],&t)||!vsl_take_player_init(&player,e,&t)||!vsl_color_init(&color,t.sample_rate,amount))goto done;
    if(argc==6) {
        if(t.frames>48000*30)goto done;
        color.tap_samples=calloc((size_t)t.frames*8,sizeof(double));if(!color.tap_samples)goto done;color.tap_capacity=t.frames;
    }
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,t.sample_rate,channels))goto done;
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,t.sample_rate,1))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    snprintf(path,sizeof path,"%s_state.csv",argv[2]);state=vsl_fopen(path,"w");if(!state)goto done;
    fputs("frame,native_state_fnv1a64,events_l,events_r,mod_l_mid,mod_l_high,mod_r_mid,mod_r_high\n",state);ok=1;
    while((n=vsl_color_take(&player,e,&color,output,257,channels,sources))!=0) {
        if(!vsl_wav_write(&mix,output,n))ok=0;
        for(i=0;i<n*(unsigned)channels;++i)if(!isfinite(output[i])||fabs(output[i])>=.95)ok=0;
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)t.sample_rate);
        fprintf(state,"%" PRIu64 ",%016" PRIx64 ",%" PRIu64 ",%" PRIu64 ",%.17g,%.17g,%.17g,%.17g\n",
                e->frame,original_state(e,copy),color.events[0],color.events[1],color.last[4],color.last[5],color.last[6],color.last[7]);
        if(!ok)break;
    }
    if(e->frame!=t.frames||(!amount&&channels==2&&player.audio_hash!=t.audio_hash))ok=0;
    if(color.tap_samples) {
        snprintf(path,sizeof path,"%s_taps.f64",argv[2]);taps=vsl_fopen(path,"wb");
        if(!taps||color.tap_frames!=t.frames||fwrite(color.tap_samples,sizeof(double),(size_t)t.frames*8,taps)!=(size_t)t.frames*8)ok=0;
    }
    snprintf(path,sizeof path,"%s_meta.json",argv[2]);meta=vsl_fopen(path,"w");if(!meta) { ok=0;goto done; }
    fprintf(meta,"{\"experiment\":\"event_color_v1\",\"base_runtime\":\"%s\",\"amount\":%.17g,\"frames\":%" PRIu64 ",\"channels\":%d,\"events_l\":%" PRIu64 ",\"events_r\":%" PRIu64 ",\"rejected_observed_events\":%" PRIu64 ",\"max_modulation\":%.17g,\"audio_hash\":\"%016" PRIx64 "\",\"native_take_hash\":\"%016" PRIx64 "\"}",
            VSL_VERSION,amount,e->frame,channels,color.events[0],color.events[1],color.denied_events,color.max_mod,player.audio_hash,t.audio_hash);
    printf("event_color_v1 | base%s | amount%.3f | frames%" PRIu64 " | %s\n",VSL_VERSION,amount,e->frame,ok?"pass":"FAIL");
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(state) { if(ferror(state))ok=0;if(fclose(state))ok=0; }
    if(taps) { if(ferror(taps))ok=0;if(fclose(taps))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    free(color.tap_samples);vsl_take_free(&t);free(e);free(copy);return ok?0:2;
}
