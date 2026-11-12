#include "models.h"
#include "resonant_detail_io/profile.h"
#include <stdlib.h>
RssConfig rsm_assets_config(const RsmAssets *a) {
    RssConfig c={0};
    c.source.dna=&a->prepared;c.source.low=a->has_low?&a->low:NULL;
    c.source.dna_seed=c.source.low_seed=48271;c.source.low_scale=1.6658265329883064;
    c.detail=a->has_detail?&a->detail:NULL;c.detail_seed=8121907;return c;
}
RsmControl rsm_assets_control(const RsmAssets *a) {
    RsmControl p={{{1,1,1,1,0,0},0},.5,1};
    p.source.source.low_gain=a->has_low?1:0;p.source.detail_gain=a->has_detail?1:0;return p;
}
int rsm_assets_load(RsmAssets *out,int selection) {
    RsmAssets *a;RssVoice *trial;RssConfig cfg;RsmControl ctl;RssColour colour={0,1200,1900};int ok=0;
    if(!out||selection<0||selection>4)return 0;
    a=calloc(1,sizeof *a);trial=calloc(1,sizeof *trial);
    if(!a||!trial)goto done;
    a->selection=selection;a->has_low=selection>=3;a->has_detail=selection==1||selection==2||selection==4;
    if(!sd_profile_load(a->has_low?"voices/dna_bank_v1/V10 Exterior.model":"voices/exterior_anchors_v1/A Stationary Low.model",&a->original))goto done;
    if(a->has_low&&!sd_profile_load("voices/coherent_low_v1/measured_phase.model",&a->low))goto done;
    if(a->has_detail&&!rdt_profile_load(selection==4?"voices/resonant_detail_c_v1/moving_35.rdetail":
        selection==1?"voices/resonant_detail_c_v1/idle_add.rdetail":"voices/resonant_detail_c_v1/idle_35.rdetail",&a->detail))goto done;
    if(selection==2||selection==4)colour.power_reduction=.35;
    if(!rss_profile_prepare(&a->prepared,&a->original,&colour))goto done;
    cfg=rsm_assets_config(a);ctl=rsm_assets_control(a);
    if(!rss_voice_init(trial,&cfg,&ctl.source))goto done;
    *out=*a;ok=1;
done:free(a);free(trial);return ok;
}
