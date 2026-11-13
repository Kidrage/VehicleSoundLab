#include "source.h"
#include "study.h"
#include <string.h>
static int tick(void *state,const AdSourceContext *context,AdSourceFrame *frame) {
    IsSource *s=state;unsigned layer,c;
    int gate=s->enabled&&context->drive->lifecycle==VSL_RUNNING&&context->drive->operating==VSL_IDLE;
    if(context->frame!=s->voice.frame||(s->capture&&s->capture_count>=s->capture_capacity)||
       !ml_voice_tick(&s->voice,gate,context->envelope,&s->latest))return 0;
    if(s->capture)s->capture[s->capture_count++]=s->latest;
    s->latest_gate=gate;if(gate)++s->enabled_samples;
    if(s->latest.weight==0)return 1; /* Preserve original stems exactly. */
    for(layer=0;layer<AD_SOURCE_ADDED;++layer)for(c=0;c<2;++c)frame->stereo[layer][c]*=s->latest.keep;
    for(c=0;c<2;++c)frame->stereo[AD_SOURCE_ADDED][c]+=s->latest.output[c];
    return 1;
}
int is_source_init(IsSource *s,const MiModels *m,uint64_t seed,int enabled) {
    MlProfile p;
    if(!s||(enabled!=0&&enabled!=1)||!mi_models_valid(m))return 0;
    memset(&p,0,sizeof p);p.modal=&m->modal;p.detail=&m->detail;
    p.modal_ratio=p.modal_gain=p.detail_gain=1;p.level_gain=IS_IDLE_LEVEL_GAIN;
    p.attack_frames=p.release_frames=IS_IDLE_FADE_FRAMES;
    if(!ml_profile_valid(&p))return 0;
    memset(s,0,sizeof *s);s->profile=p;s->enabled=enabled;
    if(!ml_voice_init(&s->voice,&s->profile,seed))return 0;
    s->processor.state=s;s->processor.tick=tick;return 1;
}
