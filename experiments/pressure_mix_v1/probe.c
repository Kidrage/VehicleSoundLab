#define _CRT_SECURE_NO_WARNINGS
#include "observer.h"
#include "io/take_file.h"
#include "io/wav.h"
#include "io/file.h"
#include "io/drive_trace.h"
#include "spatial/scene.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>

static uint64_t control_hash(const VslEngine *e,VslEngine *copy) {
    const unsigned char *bytes;size_t i;uint64_t h=VSL_TAKE_HASH_INITIAL;
    /* Only audio histories/output can depend on replaced pressure. Everything
       else, including original character state/RNG, must stay byte-identical. */
    memcpy(copy,e,sizeof *copy);
    memset(&copy->acoustics,0,sizeof copy->acoustics);
    memset(&copy->spatial,0,sizeof copy->spatial);
    memset(&copy->objects,0,sizeof copy->objects);copy->peak=0;
    bytes=(const unsigned char *)copy;
    for(i=0;i<sizeof *copy;++i) { h^=bytes[i];h*=UINT64_C(1099511628211); }
    return h;
}
int main(int argc,char **argv) {
    VslTake take={0};VslTakePlayer player;VslEngine *e=NULL,*copy=NULL;
    VslPressureObserver observer={0};VslWavWriter mix={0},stems[VSL_OBJECTS]={0};
    FILE *trace=NULL,*states=NULL,*samples=NULL,*replacement=NULL,*meta=NULL;
    double *replacement_data=NULL;float output[257*12],sources[257*VSL_OBJECTS],mono[257];
    char path[4096],*end;int mode,channels,c,ok=0;unsigned n,i;
    const VslCharacterProfile *profile=vsl_character_profile();
    if((argc!=5&&argc!=6)||strlen(argv[2])>3800)return 1;
    mode=(int)strtol(argv[3],&end,10);if(end==argv[3]||*end||mode<0||mode>2)return 1;
    channels=(int)strtol(argv[4],&end,10);if(end==argv[4]||*end||(channels!=2&&channels!=12))return 1;
    if((mode==2)!=(argc==6))return 1;
    e=malloc(sizeof *e);copy=malloc(sizeof *copy);
    if(!e||!copy||!vsl_take_load(argv[1],&take)||!vsl_take_player_init(&player,e,&take))goto done;
    observer.frames=take.frames;
    for(i=0;i<take.count;++i)if(take.events[i].params.profile!=VSL_V10||take.assets.dna_count)goto done;
    if(mode) {
        observer.samples=calloc((size_t)take.frames*3,sizeof(double));if(!observer.samples)goto done;
        snprintf(path,sizeof path,"%s_events.csv",argv[2]);observer.events=vsl_fopen(path,"w");if(!observer.events)goto done;
        fputs("frame,bank,gain,shape,elapsed\n",observer.events);
        snprintf(path,sizeof path,"%s_samples.f64",argv[2]);samples=vsl_fopen(path,"wb");if(!samples)goto done;
    }
    if(mode==2) {
        replacement=vsl_fopen(argv[5],"rb");if(!replacement)goto done;
        replacement_data=malloc((size_t)take.frames*2*sizeof(double));if(!replacement_data)goto done;
        if(fread(replacement_data,sizeof(double),(size_t)take.frames*2,replacement)!=(size_t)take.frames*2||fgetc(replacement)!=EOF)goto done;
        for(i=0;i<take.frames*2;++i)if(!isfinite(replacement_data[i]))goto done;
        observer.replacement=replacement_data;
    }
    snprintf(path,sizeof path,"%s.wav",argv[2]);if(!vsl_wav_begin_float(&mix,path,take.sample_rate,channels))goto done;
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,take.sample_rate,1))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    snprintf(path,sizeof path,"%s_state.csv",argv[2]);states=vsl_fopen(path,"w");if(!states)goto done;fputs("frame,unchanged_state_fnv1a64\n",states);
    ok=1;
    for(;;) {
        n=mode?vsl_cf_take(&player,e,&observer,output,257,channels,sources):vsl_take_process(&player,e,output,257,channels,sources);
        if(!n)break;
        if(!vsl_wav_write(&mix,output,n))ok=0;
        for(i=0;i<n*(unsigned)channels;++i)if(!isfinite(output[i])||fabs(output[i])>=.95)ok=0;
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)take.sample_rate);
        fprintf(states,"%" PRIu64 ",%016" PRIx64 "\n",e->frame,control_hash(e,copy));
        if(!ok)break;
    }
    if(e->frame!=take.frames||observer.error||observer.resets||(mode<2&&channels==2&&player.audio_hash!=take.audio_hash))ok=0;
    if(samples&&fwrite(observer.samples,sizeof(double),(size_t)take.frames*3,samples)!=(size_t)take.frames*3)ok=0;
    snprintf(path,sizeof path,"%s_meta.json",argv[2]);meta=vsl_fopen(path,"w");if(!meta) { ok=0;goto done; }
    fprintf(meta,"{\"base_runtime\":\"%s\",\"mode\":%d,\"channels\":%d,\"sample_rate\":%u,\"frames\":%" PRIu64 ",\"strikes\":%" PRIu64 ",\"resets\":%u,\"take_audio_hash\":\"%016" PRIx64 "\",\"render_audio_hash\":\"%016" PRIx64 "\",\"shape_spread\":%.17g,\"right_delay_seconds\":%.17g,\"modes\":[",
        VSL_VERSION,mode,channels,take.sample_rate,e->frame,observer.strikes,observer.resets,take.audio_hash,player.audio_hash,profile->shape_spread,vsl_profile(VSL_V10)->bank_delay);
    for(c=0;c<VSL_CHARACTER_PRESSURE_MODES;++c)fprintf(meta,"%s{\"hz\":%.17g,\"decay_seconds\":%.17g,\"weight\":%.17g}",c?",":"",profile->pressure[c].hz,profile->pressure[c].decay,profile->pressure[c].weight);
    fputs("]}",meta);
    printf("pressure_mix_v1 | native %s | mode %d | frames %" PRIu64 " | channels %d | strikes %" PRIu64 " | %s\n",VSL_VERSION,mode,e->frame,channels,observer.strikes,ok?"pass":"FAIL");
done:
    if(meta) { if(ferror(meta))ok=0;if(fclose(meta))ok=0; }
    if(observer.events) { if(ferror(observer.events))ok=0;if(fclose(observer.events))ok=0; }
    if(samples&&fclose(samples))ok=0;if(replacement&&fclose(replacement))ok=0;
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    if(states) { if(ferror(states))ok=0;if(fclose(states))ok=0; }
    if(mix.file)ok=vsl_wav_end(&mix)&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    free(observer.samples);free(replacement_data);vsl_take_free(&take);free(e);free(copy);return ok?0:2;
}
