#include "catalog.h"
#include <stdlib.h>
struct DcPreset {int selection;AtAssets assets;AdControl initial;};
static const DcInfo info[DC_COUNT]={
    {"v10-moving-fine-idle","V10 · 行驶35%＋细谱怠速候选","A moving exterior + F2 fixed idle; engineering blend, not same-car full state calibration",VSL_V10},
    {"v10-moving35","V10 · 行驶35%完整配方（局部）","Accepted fixed moving context; driving RPM/load mapping provisional",VSL_V10},
    {"v10-exterior4","V10 · 驻车车外四锚点（实验）","A stationary exterior; four acoustic anchors, not full measured RPM/load coverage",VSL_V10},
    {"v10-cabin2","V10 · 高转车内双锚点（实验）","E high-RPM cabin; separate observation from exterior",VSL_V10},
    {"v10-start-settle","V10 · 启动趋稳（实验）","A cabin startup/catch/settle with existing local residual; not hot-idle calibration",VSL_V10},
    {"synthetic-warm","合成 · Warm Additive（工程示例）","Analytic DNA fixture, not a measured engine or user Serum patch",VSL_SCIFI},
    {"synthetic-hollow","合成 · Hollow Spectrum（工程示例）","Analytic DNA fixture, not a measured engine or user Serum patch",VSL_SCIFI}
};
static const char *aux_names[DC_AUX_COUNT]={"进气","机械","排气空气","道路","风","启动机械声","接火低频","怠速声线（候选）","怠速主声线起伏","怠速细谱纹理"};
const DcInfo *dc_info(int selection){return selection>=0&&selection<DC_COUNT?info+selection:NULL;}
DcPreset *dc_preset_create(int selection,const AdConfig *cfg,const AdControl *initial) {
    DcPreset *p;const DcInfo *meta=dc_info(selection);
    if(!meta||!cfg||!initial||cfg->profile!=meta->profile||!ad_control_supported(cfg,initial))return NULL;
    p=calloc(1,sizeof *p);if(!p)return NULL;
    if(!at_assets_copy(&p->assets,cfg)){free(p);return NULL;}
    p->selection=selection;p->initial=*initial;return p;
}
void dc_preset_destroy(DcPreset *p){free(p);}
const AdConfig *dc_preset_config(const DcPreset *p){return p?&p->assets.config:NULL;}
AdControl dc_preset_initial(const DcPreset *p){AdControl zero={0};return p?p->initial:zero;}
int dc_preset_selection(const DcPreset *p){return p?p->selection:-1;}
int dc_aux_enabled(const AdConfig *c,int layer) {
    if(!c||layer<0||layer>=DC_AUX_COUNT)return 0;
    if(layer<DC_STARTUP)return 1;
    switch(layer){
    case DC_STARTUP:return c->startup_profile!=NULL;
    case DC_CATCH:return c->catch_profile!=NULL;
    case DC_IDLE:return c->idle_profile||c->fine_idle_profile;
    default:return c->fine_idle_profile!=NULL;
    }
}
const char *dc_aux_name(int layer){return layer>=0&&layer<DC_AUX_COUNT?aux_names[layer]:NULL;}
double *dc_aux_amount(AdControl *c,int layer) {
    if(!c)return NULL;
    switch(layer){
    case DC_INTAKE:return &c->mix.intake_gain;
    case DC_MECHANICAL:return &c->mix.mechanical_gain;
    case DC_AIR:return &c->mix.air_gain;
    case DC_ROAD:return &c->mix.road_gain;
    case DC_WIND:return &c->mix.wind_gain;
    case DC_STARTUP:return &c->mix.startup_gain;
    case DC_CATCH:return &c->mix.catch_gain;
    case DC_IDLE:return &c->mix.idle_mix;
    case DC_MOTION:return &c->mix.idle_motion;
    case DC_FINE:return &c->mix.idle_detail;
    default:return NULL;
    }
}
