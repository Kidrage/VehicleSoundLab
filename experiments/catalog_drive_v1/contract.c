#include "models.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"catalog contract%d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(void) {
    CHECK(!dc_info(-1)&&!dc_info(DC_COUNT)&&!cd_models_load(-1)&&!cd_models_load(DC_COUNT));
    CHECK(!dc_preset_create(0,NULL,NULL)&&!dc_preset_config(NULL)&&dc_preset_selection(NULL)==-1);
    CHECK(!dc_aux_enabled(NULL,DC_IDLE)&&!dc_aux_amount(NULL,0)&&!dc_aux_name(DC_AUX_COUNT));
    for(int k=0;k<DC_COUNT;++k) {
        DcPreset *p=cd_models_load(k);const DcInfo *meta=dc_info(k);AdConfig bad;AdControl c;const AdConfig *cfg;
        CHECK(p&&meta&&meta->key[0]&&meta->title[0]&&meta->scope[0]);cfg=dc_preset_config(p);c=dc_preset_initial(p);
        CHECK(cfg&&cfg->profile==meta->profile&&dc_preset_selection(p)==k&&!c.drive.ignition&&ad_control_supported(cfg,&c));
        CHECK(cfg->bank->count==(k==DC_EXTERIOR?4u:k==DC_CABIN?2u:1u));
        CHECK((cfg->fine_idle_profile!=NULL)==(k==DC_FINE_IDLE));
        CHECK((cfg->recipe_bank!=NULL)==(k<=DC_MOVING));
        CHECK(dc_aux_enabled(cfg,DC_STARTUP)==(k==DC_SETTLE)&&dc_aux_enabled(cfg,DC_CATCH)==(k==DC_SETTLE));
        CHECK(dc_aux_enabled(cfg,DC_IDLE)==(k==DC_FINE_IDLE)&&dc_aux_enabled(cfg,DC_FINE)==(k==DC_FINE_IDLE));
        bad=*cfg;bad.profile=cfg->profile==VSL_V10?VSL_SCIFI:VSL_V10;CHECK(!dc_preset_create(k,&bad,&c));
        bad=*cfg;bad.root_per_rpm=-1;CHECK(!dc_preset_create(k,&bad,&c));
        for(int j=0;j<k;++j)CHECK(strcmp(meta->key,dc_info(j)->key));
        CHECK(!dc_aux_amount(&c,-1)&&!dc_aux_amount(&c,DC_AUX_COUNT));
        dc_preset_destroy(p);
    }
    puts("PASS7 owned typed recipes, unique metadata, real capabilities, invalid config rejection and existing source contexts");return 0;
}
