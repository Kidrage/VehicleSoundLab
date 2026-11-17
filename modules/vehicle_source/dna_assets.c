#include "internal.h"
#include "dna_assets.h"
#include <math.h>
#include <stdlib.h>
VsAssets *vs_assets_from_dna(const VsDnaConfig *c) {
    VsAssets *a;unsigned k;const SdProfile *models[SA_MAX_ANCHORS];
    if(!c||!c->anchors||!c->count||c->count>SA_MAX_ANCHORS||c->align_orders>32||!c->seed||
       c->vehicle_profile<0||c->vehicle_profile>=VSL_PROFILE_COUNT||!isfinite(c->root_per_rpm)||
       c->root_per_rpm<=0||c->root_per_rpm>.1)return NULL;
    for(k=0;k<c->count;++k)if(!c->anchors[k])return NULL;
    a=calloc(1,sizeof *a);if(!a)return NULL;
    for(k=0;k<c->count;++k){a->owned.profile[k]=*c->anchors[k];models[k]=&a->owned.profile[k];}
    if(!sa_bank_init(&a->owned.bank,models,c->count,c->align_orders)){free(a);return NULL;}
    a->owned.config.bank=&a->owned.bank;a->owned.config.seed=c->seed;
    a->owned.config.profile=c->vehicle_profile;a->owned.config.channels=2;
    a->owned.config.root_per_rpm=c->root_per_rpm;a->owned.config.scene_mode=AD_SCENE_STEREO_BED;
    if(!at_assets_valid(&a->owned)){free(a);return NULL;}
    return a;
}
