#include "source.h"
#include <math.h>
int ad_source_valid(const AdSourceProcessor *p) { return !p||(p->state&&p->tick); }
int ad_source_apply(const AdSourceProcessor *p,const AdSourceContext *c,AdSourceFrame *out) {
    AdSourceFrame f;unsigned layer,ch;
    if(!c||!c->drive||!out||!ad_source_valid(p))return 0;
    if(!p)return 1;
    f=*out;if(!p->tick(p->state,c,&f))return 0;
    for(layer=0;layer<AD_SOURCE_LAYERS;++layer)for(ch=0;ch<2;++ch)
        if(!isfinite(f.stereo[layer][ch]))return 0;
    *out=f;return 1;
}
