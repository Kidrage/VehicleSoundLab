#define _CRT_SECURE_NO_WARNINGS
#include "audition.h"
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
static int metadata(const char *path,const VslSourceAudition *state) {
    FILE *f=vsl_fopen(path,"w");int g,m,c,ok;
    if(!f)return 0;
    fprintf(f,"{\"schema\":\"vsl.source-audition/1\",\"base_runtime\":\"%s\",\"groups\":[",VSL_VERSION);
    for(g=0;g<VSL_AUDITION_GROUPS;++g) {
        unsigned mask=vsl_audition_group_mask(g);int first=1;
        fprintf(f,"%s{\"name\":\"%s\",\"mask\":%u,\"objects\":[",g?",":"",vsl_audition_group_name(g),mask);
        for(c=0;c<VSL_OBJECTS;++c)if(mask&(1u<<c)) {
            fprintf(f,"%s\"%s\"",first?"":",",vsl_object_info(c)->name);first=0;
        }
        fprintf(f,"]}");
    }
    fprintf(f,"],\"modes\":[");
    for(m=0;m<VSL_AUDITION_MODES;++m) {
        char name[80];if(!vsl_audition_mode_name(m,name,sizeof name)) { fclose(f);return 0; }
        fprintf(f,"%s{\"id\":%d,\"name\":\"%s\",\"clipped_samples\":%" PRIu64 "}",m?",":"",m,name,state->clipped[m]);
    }
    fprintf(f,"],\"semantics\":\"Fixed acoustic-object groups after source IR construction. Independent spatial histories, native full mix unchanged. Solo plus without equals full before output clamp, up to floating precision. No excitation switches or new voicing.\"}\n");
    ok=!ferror(f);if(fclose(f))ok=0;return ok;
}
int main(int argc,char **argv) {
    VslTake take={0};VslTakePlayer player;VslEngine *e=NULL;VslSourceAudition *observer=NULL;
    VslWavWriter mixes[VSL_AUDITION_MODES]={0},stems[VSL_OBJECTS]={0};FILE *trace=NULL;
    float output[257*12],sources[257*VSL_OBJECTS],views[257*VSL_AUDITION_MODES*12],block[257*12],mono[257];
    unsigned n,i;int channels,m,c,ok=0;char path[4096],name[80],*end;
    if(argc!=4||strlen(argv[2])>3800)return 1;
    channels=(int)strtol(argv[3],&end,10);if(end==argv[3]||*end||(channels!=2&&channels!=12))return 1;
    e=malloc(sizeof *e);observer=malloc(sizeof *observer);
    if(!e||!observer||!vsl_take_load(argv[1],&take)||!vsl_take_player_init(&player,e,&take))goto done;
    vsl_audition_init(observer);
    for(m=0;m<VSL_AUDITION_MODES;++m) {
        if(!vsl_audition_mode_name(m,name,sizeof name))goto done;
        snprintf(path,sizeof path,"%s_%s.wav",argv[2],name);
        if(!vsl_wav_begin_float(&mixes[m],path,take.sample_rate,channels))goto done;
    }
    for(c=0;c<VSL_OBJECTS;++c) {
        snprintf(path,sizeof path,"%s_source_%s.wav",argv[2],vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],path,take.sample_rate,1))goto done;
    }
    snprintf(path,sizeof path,"%s.csv",argv[2]);trace=vsl_fopen(path,"w");if(!trace)goto done;vsl_trace_header(trace);
    ok=1;
    while((n=vsl_audition_take_process(&player,e,observer,output,257,channels,sources,views))!=0) {
        for(m=0;m<VSL_AUDITION_MODES;++m) {
            for(i=0;i<n;++i)for(c=0;c<channels;++c)block[i*channels+c]=views[(i*VSL_AUDITION_MODES+m)*channels+c];
            if(!vsl_wav_write(&mixes[m],block,n))ok=0;
        }
        for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=sources[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        vsl_trace_frame(trace,e,e->frame/(double)take.sample_rate);
        if(!ok)break;
    }
    if(e->frame!=take.frames||(channels==2&&player.audio_hash!=take.audio_hash))ok=0;
    for(m=0;m<VSL_AUDITION_MODES;++m)if(observer->clipped[m])ok=0;
    snprintf(path,sizeof path,"%s_groups.json",argv[2]);if(!metadata(path,observer))ok=0;
    snprintf(path,sizeof path,"%s_scene.json",argv[2]);
    snprintf(name,sizeof name,"source");
    { char prefix[4096];snprintf(prefix,sizeof prefix,"%s_source",argv[2]);if(!vsl_write_scene_metadata(path,&e->target,channels,prefix))ok=0; }
    printf("source_audition_v1 | native %s | frames %" PRIu64 " | channels %d | full hash %016" PRIx64 " | %s\n",VSL_VERSION,e->frame,channels,player.audio_hash,ok?"pass":"FAIL");
done:
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    for(m=0;m<VSL_AUDITION_MODES;++m)if(mixes[m].file)ok=vsl_wav_end(&mixes[m])&&ok;
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    vsl_take_free(&take);free(observer);free(e);return ok?0:2;
}
