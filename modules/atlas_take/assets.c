#include "assets.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define PI 3.14159265358979323846
void at_assets_bind(AtAssets *a,int residual) {
    unsigned i;
    a->config.bank=&a->bank;a->config.residual_bank=residual?&a->residual:NULL;
    for(i=0;i<a->bank.count&&i<SA_MAX_ANCHORS;++i)a->bank.profile[i]=&a->profile[i];
}
int at_assets_valid(const AtAssets *a) {
    SaBank *check;const SdProfile *models[SA_MAX_ANCHORS];
    unsigned i,h,c;int ok=0;
    if(!a||a->config.source_processor||!a->bank.count||a->bank.count>SA_MAX_ANCHORS||a->config.bank!=&a->bank||
        !a->config.seed||a->config.profile<0||a->config.profile>=VSL_PROFILE_COUNT||
        (a->config.channels!=2&&a->config.channels!=12)||!isfinite(a->config.root_per_rpm)||
        a->config.root_per_rpm<=0||a->config.root_per_rpm>.1||
        !ds_routing_valid(a->config.projection,a->config.route)||
        (a->config.scene_mode!=AD_SCENE_OBJECTS&&a->config.scene_mode!=AD_SCENE_STEREO_BED))return 0;
    if(a->config.startup_profile&&(a->config.startup_profile!=&a->startup||!st_profile_valid(&a->startup)))return 0;
    if(a->config.catch_profile&&(a->config.catch_profile!=&a->catch_bloom||!cb_profile_valid(&a->catch_bloom)))return 0;
    if(a->config.resonant_bank&&(a->config.resonant_bank!=&a->resonant||!drs_bank_valid(&a->resonant,&a->bank)))return 0;
    if(a->config.recipe_bank&&(a->config.recipe_bank!=&a->recipe||!drc_bank_valid(&a->recipe,&a->bank,a->config.resonant_bank)))return 0;
    if(a->config.idle_profile&&(a->config.idle_profile!=&a->idle||a->idle.modal!=&a->idle_modal||
       a->idle.detail!=&a->idle_detail||!ml_profile_valid(&a->idle)))return 0;
    if(a->config.fine_idle_profile&&(a->config.idle_profile||a->config.fine_idle_profile!=&a->fine_idle||
       a->fine_idle.modal!=&a->fine_modal||a->fine_idle.motion!=&a->fine_motion||
       a->fine_idle.detail!=&a->fine_detail||!fi_profile_valid(&a->fine_idle)))return 0;
    if(a->config.residual_bank) {
        if(a->config.residual_bank!=&a->residual||!ra_bank_valid(&a->residual)||a->residual.count!=a->bank.count)return 0;
        for(i=0;i<a->bank.count;++i)if(fabs(a->residual.root[i]-a->profile[i].base_hz)>1e-8)return 0;
    }
    for(i=0;i<a->bank.count;++i){if(a->bank.profile[i]!=&a->profile[i])return 0;models[i]=&a->profile[i];}
    check=calloc(1,sizeof *check);if(!check)return 0;
    if(!sa_bank_init(check,models,a->bank.count,0)||a->bank.harmonics!=check->harmonics)goto done;
    for(i=0;i<=SA_TABLE_SIZE;++i)if(a->bank.sine[i]!=check->sine[i])goto done;
    for(i=0;i<a->bank.count;++i) {
        if(!isfinite(a->bank.offset[i])||fabs(a->bank.offset[i])>PI)goto done;
        for(h=0;h<a->bank.harmonics;++h)for(c=0;c<2;++c) {
            double phase=a->bank.phase[i][h][c],re=a->bank.unit[i][h][2*c],im=a->bank.unit[i][h][2*c+1];
            if(!isfinite(phase)||fabs(phase)>PI||!isfinite(re)||!isfinite(im)||
                fabs(re-cos(phase))>1e-12||fabs(im-sin(phase))>1e-12)goto done;
            if(i) {
                double d=a->bank.delta[i-1][h][c];
                if(!isfinite(d)||fabs(d)>2*PI||fabs(remainder(phase-a->bank.phase[i-1][h][c]-d,2*PI))>1e-10)goto done;
            }
        }
    }
    ok=1;
done:free(check);return ok;
}
int at_assets_copy(AtAssets *to,const AdConfig *from) {
    unsigned i;
    /* Opaque experimental source state is not represented by schema10. Reject
       before mutation, rather than producing a take that replays another sound. */
    if(!to||!from||from->source_processor||(from->fine_idle_profile&&from->idle_profile)||
       !from->bank||!from->bank->count||from->bank->count>SA_MAX_ANCHORS)return 0;
    memset(to,0,sizeof *to);to->config=*from;to->bank=*from->bank;
    for(i=0;i<from->bank->count;++i){if(!from->bank->profile[i])return 0;to->profile[i]=*from->bank->profile[i];}
    if(from->residual_bank)to->residual=*from->residual_bank;
    if(from->startup_profile){to->startup=*from->startup_profile;to->config.startup_profile=&to->startup;}
    if(from->catch_profile){to->catch_bloom=*from->catch_profile;to->config.catch_profile=&to->catch_bloom;}
    if(from->resonant_bank){to->resonant=*from->resonant_bank;to->config.resonant_bank=&to->resonant;}
    if(from->recipe_bank){to->recipe=*from->recipe_bank;to->config.recipe_bank=&to->recipe;}
    if(from->idle_profile) {
        if(!ml_profile_valid(from->idle_profile))return 0;
        to->idle=*from->idle_profile;to->idle_modal=*to->idle.modal;to->idle_detail=*to->idle.detail;
        to->idle.modal=&to->idle_modal;to->idle.detail=&to->idle_detail;to->config.idle_profile=&to->idle;
    }
    if(from->fine_idle_profile) {
        if(from->idle_profile||!fi_profile_valid(from->fine_idle_profile))return 0;
        to->fine_idle=*from->fine_idle_profile;to->fine_modal=*to->fine_idle.modal;
        to->fine_motion=*to->fine_idle.motion;to->fine_detail=*to->fine_idle.detail;
        to->fine_idle.modal=&to->fine_modal;to->fine_idle.motion=&to->fine_motion;
        to->fine_idle.detail=&to->fine_detail;to->config.fine_idle_profile=&to->fine_idle;
    }
    at_assets_bind(to,from->residual_bank!=NULL);
    return at_assets_valid(to);
}
