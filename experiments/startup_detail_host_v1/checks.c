#include "../atlas_monitor_v1/models.h"
#include "atlas_take/assets.h"
#include "atlas_take/parameters.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"startup detail host line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static AmModels plain,variant,expected;static SaBank bank;
int main(int argc,char **argv) {
    unsigned i,count;AtAssets *assets;AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    CHECK(argc==1||(argc==2&&!strcmp(argv[1],"--missing-detail")));
    if(argc==2) {
        CHECK(am_models_load(&plain,2));expected=plain;
        CHECK(!am_models_load_variant(&plain,2,1)&&!memcmp(&plain,&expected,sizeof plain));return 0;
    }
    for(i=0;i<3;++i) {
        CHECK(am_models_load(&plain,(int)i)&&am_models_load_variant(&variant,(int)i,0));
        CHECK(!memcmp(&plain,&variant,sizeof plain));
        if(i<2){CHECK(am_models_load_variant(&variant,(int)i,1));CHECK(!memcmp(&plain,&variant,sizeof plain));}
    }
    CHECK(plain.count==1&&plain.residual.count==0);
    CHECK(am_models_load_variant(&variant,2,1)&&variant.count==1&&variant.residual.count==1);
    CHECK(!memcmp(plain.profile,variant.profile,sizeof plain.profile));
    CHECK(variant.residual.profile[0].bands==12&&variant.residual.profile[0].band[2].power[0]==0&&
          variant.residual.profile[0].band[2].power[1]==0&&ra_bank_valid(&variant.residual));
    expected=variant;CHECK(!am_models_load_variant(&variant,2,2)&&!memcmp(&variant,&expected,sizeof variant));
    CHECK(!am_models_load_variant(&variant,3,1)&&!memcmp(&variant,&expected,sizeof variant));
    CHECK(am_models_bank(&variant,&bank));config.residual_bank=&variant.residual;
    assets=calloc(1,sizeof *assets);CHECK(assets&&at_assets_copy(assets,&config));
    memset(&variant,0,sizeof variant);memset(&bank,0,sizeof bank);
    CHECK(at_assets_valid(assets)&&assets->config.residual_bank==&assets->residual&&assets->residual.count==1);
    CHECK(assets->residual.profile[0].bands==12);free(assets);
    {const AtField *fields=at_fields(&count);CHECK(count==29&&!strcmp(fields[26].name,"catch_gain")&&!strcmp(fields[27].name,"resonant_gain"));}
    puts("PASS: startup detail context/transaction/owned12band assets");return 0;
}
