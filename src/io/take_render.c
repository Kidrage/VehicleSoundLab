#include "take_render.h"
#include "wav.h"
#include "file.h"
#include "drive_trace.h"
#include "spatial/scene.h"
#include <stdlib.h>
int vsl_take_render(const VslTake *t,const char *path,int channels,const char *trace_path,const char *stem_prefix,uint64_t *hash) {
    VslEngine *e=malloc(sizeof *e);VslTakePlayer player;VslWavWriter wav={0},stems[VSL_OBJECTS]={0};
    float out[257*12],objects[257*VSL_OBJECTS],mono[257];FILE *trace=NULL;int ok=0,c;unsigned n,i;
    if(!e||(channels!=2&&channels!=12)||!vsl_take_player_init(&player,e,t))goto done;
    if(!vsl_wav_begin_float(&wav,path,t->sample_rate,channels))goto done;
    if(trace_path) { trace=vsl_fopen(trace_path,"w");if(!trace)goto done;vsl_trace_header(trace); }
    if(stem_prefix)for(c=0;c<VSL_OBJECTS;++c) {
        char name[4096];snprintf(name,sizeof name,"%s_%s.wav",stem_prefix,vsl_object_info(c)->name);
        if(!vsl_wav_begin_float(&stems[c],name,t->sample_rate,1))goto done;
    }
    ok=1;
    while((n=vsl_take_process(&player,e,out,257,channels,stem_prefix?objects:NULL))!=0) {
        if(!vsl_wav_write(&wav,out,n)) { ok=0;break; }
        if(trace)vsl_trace_frame(trace,e,e->frame/(double)t->sample_rate);
        if(stem_prefix)for(c=0;c<VSL_OBJECTS;++c) {
            for(i=0;i<n;++i)mono[i]=objects[i*VSL_OBJECTS+c];
            if(!vsl_wav_write(&stems[c],mono,n))ok=0;
        }
        if(!ok)break;
    }
    if(e->frame!=t->frames||(channels==2&&player.audio_hash!=t->audio_hash))ok=0;
    if(hash)*hash=player.audio_hash;
done:
    if(trace) { if(ferror(trace))ok=0;if(fclose(trace))ok=0; }
    for(c=0;c<VSL_OBJECTS;++c)if(stems[c].file)ok=vsl_wav_end(&stems[c])&&ok;
    if(wav.file)ok=vsl_wav_end(&wav)&&ok;free(e);return ok;
}
