#ifndef VSL_RESONANT_MONITOR_MODELS_H
#define VSL_RESONANT_MONITOR_MODELS_H
#include "resonant_monitor/render.h"
typedef struct {
    SdProfile original,prepared,low;RdtProfile detail;
    int selection,has_low,has_detail;
} RsmAssets;
/* Stable owned model storage; load only with device stopped. Transactional.
   Selections0/1/2=low original/add/35,3/4=moving original/held35. */
int rsm_assets_load(RsmAssets *assets,int selection);
RssConfig rsm_assets_config(const RsmAssets *assets);
RsmControl rsm_assets_control(const RsmAssets *assets);
#endif
