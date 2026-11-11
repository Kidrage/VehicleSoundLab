#define _CRT_SECURE_NO_WARNINGS
#include "transfer.h"
#include "profile.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "io/scene_metadata.h"
#include "spatial/scene.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
static int impulse(const char *output,int rate,int mode) {
    VslEngine *e=malloc(sizeof *e);VslEnvelopeTransfer s;VslWavWriter w={0};float samples[512*2];
    unsigned pos=0,total=(unsigned)rate,i;int ok=0;
    if(!e||!vsl_envelope_init(&s,rate,mode))goto done;
    vsl_init(e,rate,48271);if(!vsl_wav_begin_float(&w,output,rate,2))goto done;ok=1;
    while(pos<total) {
        unsigned n=total-pos;if(n>512)n=512;
        for(i=0;i<n;++i) {
            VslObjectFrame o={0};if(!pos&&!i)o.sample[0]=o.sample[1]=1;
            vsl_envelope_prepare(&s,e);o.sample[0]=vsl_envelope_side_tick(&s,0,o.sample[0]);o.sample[1]=vsl_envelope_side_tick(&s,1,o.sample[1]);samples[2*i]=(float)o.sample[0];samples[2*i+1]=(float)o.sample[1];
        }
        if(!vsl_wav_write(&w,samples,n)) { ok=0;break; }pos+=n;
    }
done:if(w.file)ok=vsl_wav_end(&w)&&ok;free(e);return ok?0:2;
}
int main(int argc,char **argv) {
    VslTake t={0};VslTakePlayer player;VslEngine *e=NULL;VslEnvelopeTransfer transfer;
    VslWavWriter mix={0},stems[VSL_OBJECTS]={0},tap_writers[2]={0};FILE *trace=NULL;int ok=0,c,mode,channels;
    char path[4096],*end;float output[257*12],sources[257*VSL_OBJECTS],mono[257],taps[257*4],tap_pair[257*2];unsigned n,i;
    if(argc!=5||strlen(argv[2])>3800)return 1;
    if(!strcmp(argv[1],"impulse")) {
        int rate=(int)strtol(argv[3],&end,10);if(*end||end==argv[3])return 1;
        mode=(int)strtol(argv[4],&end,10);if(*end||end==argv[4])return 1;
        return impulse(argv[2],rate,mode);
    }
    mode=(int)strtol(argv[3],&end,10);if(*end||end==argv[3]||mode<0||mode>2)return 1;
    channels=(int)strtol(argv[4],&end,10);if(*end||end==argv[4]||(channels!=2&&channels!=12))return 1;
    e=malloc(sizeof *e);if(!e||!vsl_take_load(argv[1],&t)||!vsl_take_player_init(&player,e,&t)||!vsl_envelope_init(&transfer,t.sample_rate,mode))goto done;
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,t.sample_rate,channels))goto done;
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,t.sample_rate,1))goto done;
    }
    for(c=0;c<2;++c) {
        snprintf(path,sizeof path,"%s_fired_%s.wav",argv[2],c?"output":"input");
        if(!vsl_wav_begin_float(&tap_writers[c],path,t.sample_rate,2))goto done;
    }
    ok=1;
    while((n=vsl_envelope_take_process(&player,e,&transfer,output,257,channels,sources,taps))!=0) {
        if(!vsl_wav_write(&mix,output,n))ok=0;
        vsl_trace_frame(trace,e,e->frame/(double)t.sample_rate);
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        for(c=0;c<2;++c) {
            for(i=0;i<n;++i) { tap_pair[2*i]=taps[4*i+2*c];tap_pair[2*i+1]=taps[4*i+2*c+1]; }
            if(!vsl_wav_write(&tap_writers[c],tap_pair,n))ok=0;
        }
        if(!ok)break;
    }
    if(e->frame!=t.frames||(channels==2&&mode==0&&player.audio_hash!=t.audio_hash)||e->peak>=.95)ok=0;
    if(channels==12) {
        char prefix[4096];snprintf(prefix,sizeof prefix,"%s_source",argv[2]);
        snprintf(path,sizeof path,"%s_scene.json",argv[2]);
        if(!vsl_write_scene_metadata(path,&e->target,channels,prefix))ok=0;
    }
    printf("exhaust_envelope_v1 mode %s | base %s | frames %" PRIu64 " | channels %d | hash %016" PRIx64 " | %s\n",
        vsl_envelope_name(mode),VSL_VERSION,e->frame,channels,player.audio_hash,ok?"pass":"FAIL");
done:
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    for(c=0;c<2;++c)if(tap_writers[c].file)ok=vsl_wav_end(&tap_writers[c])&&ok;
    vsl_take_free(&t);free(e);return ok?0:2;
}
