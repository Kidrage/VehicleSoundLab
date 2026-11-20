#include <string.h>
#include "bridge.h"
#include "vehicle_source/atlas_adapter.h"
#include "vehicle_source/dna_assets.h"
#include "../catalog_drive_v1/models.h"
#include <stdlib.h>
#include "dsp_support/storage.h"
#ifdef VSL_FIXED_V10
#include "embedded/fixed_assets.h"
#endif
struct VsbHandle {
    VsAssets *assets;VsEngine *engine;VsControl control;
    unsigned capabilities;
    float stems[VS_STEMS][VS_WORK_FRAMES*2];
};
#ifdef VSL_FIXED_V10
VSL_STORAGE(vsb_handles,struct VsbHandle,1,VSL_L2_HISTORY)
#endif
unsigned vsl_source_abi(void){return 12;}
unsigned vsl_source_dna_state_size(void){return sizeof(SxTelemetry);}
int vsl_source_dna_state(VsbHandle *h,SxTelemetry *t){return h?vs_engine_state_dna(h->engine,t):0;}
unsigned vsl_source_event_policy_size(void){return sizeof(VsEventPolicy);}
unsigned vsl_source_event_policy_stats_size(void){return sizeof(VsEventPolicyStats);}
int vsl_source_event_policy_set(VsbHandle *h,const VsEventPolicy *p){return h?vs_engine_event_policy_set(h->engine,p):0;}
int vsl_source_event_policy_get(VsbHandle *h,VsEventPolicy *p){return h?vs_engine_event_policy_get(h->engine,p):0;}
int vsl_source_event_policy_stats(VsbHandle *h,VsEventPolicyStats *p){return h?vs_engine_event_policy_stats(h->engine,p):0;}
unsigned vsl_source_startup_size(void){return sizeof(VsStartupResponse);}
int vsl_source_startup_set(VsbHandle *h,const VsStartupResponse *p){return h?vs_engine_startup_set(h->engine,p):0;}
int vsl_source_startup_get(VsbHandle *h,VsStartupResponse *p){return h?vs_engine_startup_get(h->engine,p):0;}
unsigned vsl_source_control_size(void){return sizeof(VsControl);}
unsigned vsl_source_telemetry_size(void){return sizeof(VsTelemetry);}
unsigned vsl_source_event_notice_size(void){return sizeof(EsNotice);}
unsigned vsl_source_event_profile_size(void){return sizeof(EsProfile);}
int vsl_source_event_profile(VsbHandle *h,unsigned type,const EsProfile *p){return h?vs_engine_event_profile(h->engine,type,p):0;}
unsigned vsl_source_event_mask(void){return vs_event_mask();}
const char *vsl_source_event_bank_identity(void){return vs_event_bank_identity();}
unsigned vsl_source_events(VsbHandle *h,EsNotice *out,unsigned capacity){return h?vs_engine_events(h->engine,out,capacity):0;}
unsigned vsl_source_catalog_count(void){
#ifdef VSL_FIXED_V10
return 1;
#else
return DC_COUNT;
#endif
}
#ifdef VSL_FIXED_V10
const char *vsl_source_catalog_name(int s){return s==0?"V10 / Unified DNA":NULL;}
const char *vsl_source_catalog_key(int s){return s==0?"v10-moving-fine-idle":NULL;}
#else
const char *vsl_source_catalog_name(int s){const DcInfo *p=dc_info(s);return s==DC_FINE_IDLE?"V10 · 统一 DNA / 声线 + 细谱空气纹理":p?p->title:NULL;}
const char *vsl_source_catalog_key(int s){const DcInfo *p=dc_info(s);return p?p->key:NULL;}
#endif
#ifndef VSL_FIXED_V10
static unsigned capabilities(const AdConfig *c) {
    unsigned flags=0;
    if(c->residual_bank)flags|=VSB_RESIDUAL;if(c->recipe_bank)flags|=VSB_LOW;
    if(c->resonant_bank)flags|=VSB_RESONANT;if(c->startup_profile)flags|=VSB_STARTUP;
    if(c->catch_profile)flags|=VSB_CATCH;if(c->idle_profile||c->fine_idle_profile)flags|=VSB_IDLE;
    if(c->fine_idle_profile)flags|=VSB_FINE_IDLE;return flags;
}
#endif
unsigned vsl_source_capabilities(VsbHandle *h){return h?h->capabilities:0;}
unsigned vsl_source_stem_channels(unsigned k){const VsStemInfo *p=vs_stem_info(k);return p?p->channels:0;}
const char *vsl_source_stem_name(unsigned k){const VsStemInfo *p=vs_stem_info(k);return p?p->id:NULL;}
#ifdef VSL_FIXED_V10
VsbHandle *vsl_source_open(int selection) {
    VsbHandle *h;AdControl initial;
    if(selection!=DC_FINE_IDLE)return NULL;
    h=vsb_handles_acquire();if(!h)return NULL;
    h->assets=vsl_fixed_assets_acquire();
    if(!h->assets){vsb_handles_release(h);return NULL;}
    initial=vsl_fixed_initial();vs_control_from_atlas(&initial,&h->control);
    h->control.dna_unified=1;
    h->control.intake_gain=h->control.air_gain=h->control.road_gain=h->control.wind_gain=0;
    h->engine=vs_engine_create(h->assets,&h->control);
    if(!h->engine||!vs_engine_enable_start_flare(h->engine)){vsl_source_close(h);return NULL;}
    h->capabilities=VSB_LOW|VSB_RESONANT|VSB_IDLE|VSB_FINE_IDLE|VSB_START_FLARE|
        VSB_TUNING_HEADROOM|VSB_MECHANICAL_DNA|VSB_SPLIT_DYNAMICS;
    h->control.startup_gain=.5f;h->control.catch_gain=h->control.legacy_event_gain=0;
    if(!vs_engine_set(h->engine,&h->control)){vsl_source_close(h);return NULL;}
    return h;
}
void vsl_source_close(VsbHandle *h){
    if(h){vs_engine_destroy(h->engine);vsl_fixed_assets_release(h->assets);vsb_handles_release(h);}
}
VsbHandle *vsl_source_open_dna(int selection,const char *const *paths,unsigned count,
    float root_per_rpm,uint64_t seed,unsigned align_orders){
    (void)selection;(void)paths;(void)count;(void)root_per_rpm;(void)seed;(void)align_orders;return NULL;
}
VsbHandle *vsl_source_open_state_dna(int selection,const char *const *paths,const unsigned *counts,
    float root_per_rpm,uint64_t seed,unsigned align_orders,float seconds){
    (void)selection;(void)paths;(void)counts;(void)root_per_rpm;(void)seed;(void)align_orders;(void)seconds;return NULL;
}
#else
VsbHandle *vsl_source_open(int selection) {
    DcPreset *preset=cd_models_load(selection);VsbHandle *h;AdControl initial;
    if(!preset)return NULL;
    h=calloc(1,sizeof *h);if(!h){dc_preset_destroy(preset);return NULL;}
    h->capabilities=capabilities(dc_preset_config(preset));
    h->assets=vs_assets_from_atlas(dc_preset_config(preset));
    initial=dc_preset_initial(preset);vs_control_from_atlas(&initial,&h->control);
    h->control.dna_unified=1;
    h->control.intake_gain=h->control.air_gain=h->control.road_gain=h->control.wind_gain=0;
    h->capabilities|=VSB_TUNING_HEADROOM|VSB_MECHANICAL_DNA|VSB_SPLIT_DYNAMICS;
    dc_preset_destroy(preset);
    if(h->assets)h->engine=vs_engine_create(h->assets,&h->control);
    if(!h->engine){vsl_source_close(h);return NULL;}
    if(selection==DC_FINE_IDLE){
        if(!vs_engine_enable_start_flare(h->engine)){vsl_source_close(h);return NULL;}
        h->capabilities=(h->capabilities&~(VSB_STARTUP|VSB_CATCH))|VSB_START_FLARE;
        h->control.startup_gain=.5f;h->control.catch_gain=h->control.legacy_event_gain=0;
        if(!vs_engine_set(h->engine,&h->control)){vsl_source_close(h);return NULL;}
    }
    return h;
}
void vsl_source_close(VsbHandle *h) {
    if(h){vs_engine_destroy(h->engine);vs_assets_destroy(h->assets);free(h);}
}
VsbHandle *vsl_source_open_dna(int selection,const char *const *paths,unsigned count,
    float root_per_rpm,uint64_t seed,unsigned align_orders) {
    DcPreset *preset;VsbHandle *h=NULL;SdProfile *loaded=NULL;
    const SdProfile *models[SA_MAX_ANCHORS];VsDnaConfig dna={0};AdControl initial;unsigned k;
    if(!paths||!count||count>SA_MAX_ANCHORS)return NULL;
    preset=cd_models_load(selection);if(!preset)return NULL;
    loaded=calloc(count,sizeof *loaded);h=calloc(1,sizeof *h);
    if(!loaded||!h)goto done;
    for(k=0;k<count;++k){if(!paths[k]||!sd_profile_load(paths[k],loaded+k))goto done;models[k]=loaded+k;}
    dna=(VsDnaConfig){models,count,align_orders,seed,dc_preset_config(preset)->profile,root_per_rpm};
    h->assets=vs_assets_from_dna(&dna);if(!h->assets)goto done;
    initial=dc_preset_initial(preset);vs_control_from_atlas(&initial,&h->control);
    /* Optional catalog sound assets were not copied. Their gains cannot leak
       into another authored voice. Aux sources stay explicitly opt-in. */
    h->control.legacy_event_gain=h->control.low_mix=h->control.coherent_low_gain=0;
    h->control.resonant_gain=h->control.residual_gain=h->control.startup_gain=h->control.catch_gain=0;
    h->control.idle_mix=h->control.idle_motion=h->control.idle_detail=0;
    h->control.intake_gain=h->control.mechanical_gain=h->control.air_gain=h->control.road_gain=h->control.wind_gain=0;
    h->control.events.enabled=0;
    h->control.dna_unified=1;
    h->capabilities=VSB_TUNING_HEADROOM|VSB_MECHANICAL_DNA|VSB_SPLIT_DYNAMICS;
    h->engine=vs_engine_create(h->assets,&h->control);
done:
    free(loaded);dc_preset_destroy(preset);
    if(h&&!h->engine){vsl_source_close(h);h=NULL;}
    return h;
}
VsbHandle *vsl_source_open_state_dna(int selection,const char *const *paths,const unsigned *counts,
    float root_per_rpm,uint64_t seed,unsigned align_orders,float seconds) {
    DcPreset *preset;VsbHandle *h=NULL;SdProfile *loaded=NULL;
    const SdProfile *models[SX_STATES][SA_MAX_ANCHORS];VsStateDnaConfig dna={0};
    AdControl initial;unsigned s,k,total=0,index=0;
    if(!paths||!counts||!counts[0])return NULL;
    for(s=0;s<SX_STATES;++s){if(counts[s]>SA_MAX_ANCHORS)return NULL;total+=counts[s];}
    preset=cd_models_load(selection);if(!preset)return NULL;
    h=calloc(1,sizeof *h);loaded=calloc(total,sizeof *loaded);
    if(!h||!loaded)goto done;
    for(s=0;s<SX_STATES;++s){dna.anchors[s]=models[s];dna.count[s]=counts[s];
        for(k=0;k<counts[s];++k,++index){
            if(!paths[index]||!sd_profile_load(paths[index],loaded+index))goto done;
            models[s][k]=loaded+index;
        }
    }
    dna.root_per_rpm=root_per_rpm;dna.seed=seed;dna.align_orders=align_orders;
    dna.vehicle_profile=dc_preset_config(preset)->profile;dna.transition_seconds=seconds;
    h->assets=vs_assets_from_state_dna(&dna);
    initial=dc_preset_initial(preset);vs_control_from_atlas(&initial,&h->control);
    h->control.legacy_event_gain=h->control.low_mix=h->control.coherent_low_gain=0;
    h->control.resonant_gain=h->control.residual_gain=h->control.startup_gain=h->control.catch_gain=0;
    h->control.idle_mix=h->control.idle_motion=h->control.idle_detail=0;
    h->control.intake_gain=h->control.mechanical_gain=h->control.air_gain=h->control.road_gain=h->control.wind_gain=0;
    h->control.events.enabled=0;
    h->control.dna_unified=1;
    h->capabilities=VSB_TUNING_HEADROOM|VSB_MECHANICAL_DNA|VSB_SPLIT_DYNAMICS;
    if(h->assets)h->engine=vs_engine_create(h->assets,&h->control);
done:
    free(loaded);dc_preset_destroy(preset);
    if(h&&!h->engine){vsl_source_close(h);h=NULL;}
    return h;
}
#endif
int vsl_source_controls(VsbHandle *h,VsControl *c){if(!h||!c)return 0;*c=h->control;return 1;}
int vsl_source_set(VsbHandle *h,const VsControl *c) {
    if(!h||!c||!vs_engine_set(h->engine,c))return 0;h->control=*c;return 1;
}
int vsl_source_state(VsbHandle *h,VsTelemetry *t){return h&&vs_engine_telemetry(h->engine,t);}
unsigned vsl_source_channels(void){unsigned k,n=0;for(k=0;k<VS_STEMS;++k)n+=vs_stem_info(k)->channels;return n;}
static int vsl_source_process_block(VsbHandle *h,float *monitor,float *packed,unsigned frames) {
    VsOutput out={0};unsigned n,k,c,offset,width=vsl_source_channels();
    if(!h||frames>VS_BLOCK_MAX)return 0;
    /* Native API checks output overlap. Packed data is copied only after DSP. */
    if(monitor&&packed) {
        uintptr_t a=(uintptr_t)monitor,b=(uintptr_t)packed;
        size_t ma=(size_t)frames*2*sizeof(float),mb=(size_t)frames*width*sizeof(float);
        if(a>UINTPTR_MAX-ma||b>UINTPTR_MAX-mb||(a<b+mb&&b<a+ma))return 0;
    }
    out.monitor=monitor;
    if(packed)for(k=0;k<VS_STEMS;++k)out.stem[k]=h->stems[k];
    if(!vs_engine_process(h->engine,&out,frames))return 0;
    if(packed)for(n=0;n<frames;++n) {
        offset=0;
        for(k=0;k<VS_STEMS;++k) {
            unsigned channels=vs_stem_info(k)->channels;
            for(c=0;c<channels;++c)packed[n*width+offset+c]=h->stems[k][n*channels+c];
            offset+=channels;
        }
    }
    return 1;
}

int vsl_source_process(VsbHandle *h,float *monitor,float *packed,unsigned frames){
    unsigned offset=0,width=vsl_source_channels();
    if(!h||frames>VS_BLOCK_MAX)return 0;
    if(monitor&&packed){
        uintptr_t a=(uintptr_t)monitor,b=(uintptr_t)packed;
        size_t ma=(size_t)frames*2*sizeof(float),mb=(size_t)frames*width*sizeof(float);
        if(a>UINTPTR_MAX-ma||b>UINTPTR_MAX-mb||(a<b+mb&&b<a+ma))return 0;
    }
    while(offset<frames){
        unsigned n=frames-offset;if(n>VS_WORK_FRAMES)n=VS_WORK_FRAMES;
        if(!vsl_source_process_block(h,monitor?monitor+2*offset:NULL,
            packed?packed+width*offset:NULL,n))return 0;
        offset+=n;
    }
    return 1;
}

#include "dsp/diagnostics.h"
void vsl_source_modules(float *out,unsigned n){
#ifdef VSL_CAPTURE_MODULES
 vsl_diag_copy(out,n);
#else
 memset(out,0,n*20*sizeof *out);
#endif
}

#include "dsp/perf.h"
void vsl_source_perf_reset(void){vsl_source_perf_clear();}
void vsl_source_perf_write(const char *path){vsl_source_perf_dump(path);}
