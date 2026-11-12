#include "audio.h"
#include <string.h>
AdControl am_default_control(void) {
    AdControl c={{VSL_PEDALS,0,0,1,1,1,1200,.8,0,0},{.25,1,0,.7,0,0,0,0}};
    return c;
}
static int process(void *context,float *pcm,unsigned frames,int stopping) {
    AmAudio *a=context;AdControl control;uint64_t generation;AdTelemetry telemetry[512];
    AdCapture capture={0};
    if(frames>512)return -1;
    if(a->transport==2) {
        unsigned n=at_player_process(&a->player,pcm,frames,telemetry),i;
        if(n!=frames)return -1;
        if(stopping||a->cancel_release) {
            InterlockedExchange(&a->replay_result,2);
            for(i=0;i<frames;++i){float gain=(float)(480-a->cancel_release)/480;
                pcm[2*i]*=gain;pcm[2*i+1]*=gain;if(a->cancel_release<480)++a->cancel_release;}
        }
        EnterCriticalSection(&a->lock);a->control=a->player.current;a->latest=telemetry[frames-1];LeaveCriticalSection(&a->lock);
        return a->cancel_release==480||at_player_complete(&a->player)?1:0;
    }
    EnterCriticalSection(&a->lock);control=a->control;generation=a->generation;LeaveCriticalSection(&a->lock);
    if(a->transport==1&&(a->take.count>=a->take.capacity-1||a->render.frame+1024>=AT_MAX_FRAMES))stopping=1;
    if(generation!=a->adopted) {
        /* Capacity stop freezes the last adopted control and still records fade. */
        if(a->transport!=1||a->take.count<a->take.capacity-1) {
            if(a->transport==1&&!at_take_event(&a->take,a->render.frame,&control))return -1;
            if(!am_render_set(&a->render,&control))return -1;
        } else control=a->render.drive.target;
        if(a->trace_count<AM_TRACE_CAPACITY) {
            a->trace[a->trace_count].frame=a->render.frame;a->trace[a->trace_count++].control=control;
        } else ++a->trace_overflow;
        a->adopted=generation;
    }
    if(stopping&&a->stop_frame==UINT64_MAX)a->stop_frame=a->render.frame;
    if(a->transport==1) {
        a->take.stop_frame=a->stop_frame;
        capture.dna_raw=a->raw;capture.dna=a->dna;capture.residual=a->residual;capture.body=a->body;capture.events=a->events;
        capture.aux_objects=a->auxiliary;
        capture.startup=a->startup;
        capture.catch_bloom=a->catch_bloom;
        capture.resonant=a->resonant;
        capture.coherent_low_raw=a->coherent_low_raw;capture.coherent_low=a->coherent_low;
    }
    capture.telemetry=telemetry;
    if(!am_render_process(&a->render,pcm,frames,stopping,&capture))return -1;
    if(a->transport==1)a->source_hash=at_hash_sources(a->source_hash,&capture,frames);
    if(a->capture) {
        uint64_t start=a->render.frame-frames;
        if(start+frames>a->capture_frames)return -1;
        memcpy(a->capture+2*start,pcm,frames*2*sizeof(float));
    }
    EnterCriticalSection(&a->lock);a->latest=telemetry[frames-1];LeaveCriticalSection(&a->lock);
    return a->render.release==480?1:0;
}
static void submitted(void *context,unsigned frames,uint64_t hash) {
    AmAudio *a=context;
    if(a->transport==1&&!at_take_commit(&a->take,frames,hash,a->source_hash))a->take.overflow=1;
    if(a->transport==2&&at_player_complete(&a->player)&&!a->cancel_release)
        InterlockedExchange(&a->replay_result,at_player_verified(&a->player)&&hash==a->take.audio_hash?1:-1);
}
void am_audio_init(AmAudio *a,const AdConfig *config) {
    memset(a,0,sizeof *a);InitializeCriticalSection(&a->lock);a->config=*config;
    a->control=am_default_control();wo_init(&a->device,process,a);
    a->device.submitted=submitted;
}
int am_audio_control(AmAudio *a,const AdControl *c) {
    if(am_audio_replaying(a))return 0;
    if(!ad_control_valid(c,2)||(!a->config.residual_bank&&c->mix.residual_gain>0)||(!a->config.startup_profile&&c->mix.startup_gain>0)||
       (!a->config.catch_profile&&c->mix.catch_gain>0)||(!a->config.resonant_bank&&c->mix.resonant_gain>0))return 0;
    EnterCriticalSection(&a->lock);a->control=*c;++a->generation;LeaveCriticalSection(&a->lock);return 1;
}
AdControl am_audio_get(AmAudio *a) {
    AdControl c;EnterCriticalSection(&a->lock);c=a->control;LeaveCriticalSection(&a->lock);return c;
}
AdTelemetry am_audio_latest(AmAudio *a) {
    AdTelemetry t;EnterCriticalSection(&a->lock);t=a->latest;LeaveCriticalSection(&a->lock);return t;
}
int am_audio_start(AmAudio *a,int muted,uint64_t limit) {
    AdControl control;
    am_audio_stop(a);a->transport=0;control=am_audio_get(a);
    /* This device callback owns fixed stereo buffers; multichannel export is
       supported by the portable renderer through a separate offline host. */
    if(a->config.channels!=2)return 0;
    if(!am_render_init(&a->render,&a->engine,&a->config,&control))return 0;
    a->adopted=UINT64_MAX;a->stop_frame=UINT64_MAX;a->trace_count=a->trace_overflow=0;
    EnterCriticalSection(&a->lock);memset(&a->latest,0,sizeof a->latest);LeaveCriticalSection(&a->lock);
    return wo_start(&a->device,muted,limit);
}
int am_audio_record(AmAudio *a,int muted,uint64_t limit) {
    AtTake candidate={0};AdControl c;
    am_audio_stop(a);c=am_audio_get(a);
    if(a->config.channels!=2||limit>AT_MAX_FRAMES||!at_take_allocate(&candidate,AT_MAX_EVENTS))return 0;
    if(!at_take_begin(&candidate,&a->config,&c)||!am_render_init(&a->render,&a->engine,&candidate.assets->config,&c)){
        at_take_free(&candidate);return 0;}
    at_take_free(&a->take);a->take=candidate;a->ready=0;a->transport=1;a->source_hash=AT_HASH_INITIAL;
    a->adopted=UINT64_MAX;a->stop_frame=UINT64_MAX;a->trace_count=a->trace_overflow=0;
    return wo_start(&a->device,muted,limit?limit:AT_MAX_FRAMES);
}
int am_audio_replay(AmAudio *a,int muted) {
    am_audio_stop(a);
    if(!a->ready||!at_player_init(&a->player,&a->engine,&a->take,2))return 0;
    a->transport=2;a->cancel_release=0;InterlockedExchange(&a->replay_result,0);
    return wo_start(&a->device,muted,a->take.frames);
}
int am_audio_replaying(AmAudio *a) {return a->transport==2&&InterlockedCompareExchange(&a->device.running,0,0)!=0;}
void am_audio_stop(AmAudio *a) {
    wo_stop(&a->device);
    if(a->transport==1){at_take_finish(&a->take);a->ready=at_take_valid(&a->take);}
}
void am_audio_destroy(AmAudio *a) {am_audio_stop(a);wo_destroy(&a->device);at_take_free(&a->take);DeleteCriticalSection(&a->lock);}
