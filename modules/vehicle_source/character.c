#include "internal.h"
#include "core/engine.h"
#include "dna_character/dynamics.h"
void vs_character_envelopes(void *state,const VslEngine *owner,double *line,double *air) {
    (void)state;dch_dynamics_targets(owner,line,air);
}
/* The sole driver supplies state/RPM; this adapter only voices its dry DNA. */
int vs_character_sample(void *state,const AdSourceContext *ctx,AdSourceFrame *f) {
    VsEngine *s=state;const VslDrive *d=ctx->drive;unsigned k,role=DCH_CRUISE;DchFrame result;
    double air[2];DchContext c;
    if(d->lifecycle!=VSL_RUNNING)role=DCH_START;
    else if(d->operating==VSL_IDLE)role=DCH_IDLE;
    else if(d->rpm>=.95*vsl_profile(s->generator.config.profile)->max_rpm)role=DCH_LIMIT;
    else if(d->operating==VSL_OVERRUN||d->operating==VSL_SHIFT_CUT)role=DCH_OVERRUN;
    else if(d->operating==VSL_PULL||d->operating==VSL_FREE_REV||d->operating==VSL_SHIFT_RECOVER||d->operating==VSL_REV_MATCH)role=DCH_POWER;
    c=(DchContext){role,d->rpm,vsl_profile(s->generator.config.profile)->idle_rpm,ctx->envelope};
    for(k=0;k<2;++k)air[k]=f->stereo[AD_SOURCE_RESIDUAL][k]+f->stereo[AD_SOURCE_RESONANT][k];
    if(!dch_tick_split(s->character,&c,f->stereo[AD_SOURCE_DNA],air,ctx->air_envelope,&result))return 0;
    for(k=0;k<2;++k){f->stereo[AD_SOURCE_DNA][k]=result.line[k];
        f->stereo[AD_SOURCE_RESIDUAL][k]=result.air[k];f->stereo[AD_SOURCE_RESONANT][k]=0;}
    s->idle_weight=result.idle_weight;return 1;
}
