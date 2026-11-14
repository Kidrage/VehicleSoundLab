#include "assets.h"
#include "schedule.h"
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"local atlas check %d: %s\n",__LINE__,#x);return 1;}}while(0)
static LaAssets assets,saved;static LaSchedule schedule,before;
int main(int argc,char **argv) {
    unsigned a;if(argc!=5)return 2;
    CHECK(la_assets_load(&assets,argv[1])&&la_schedule_load(&schedule,argv[2]));
    CHECK(assets.bank.count==3&&schedule.count>1&&schedule.event[0].frame==0);
    for(a=0;a<assets.bank.count;++a)CHECK(assets.bank.profile[a]==assets.models+a);
    saved=assets;before=schedule;
    CHECK(!la_assets_load(&assets,argv[3])&&!memcmp(&assets,&saved,sizeof assets));
    CHECK(!la_schedule_load(&schedule,argv[4])&&!memcmp(&schedule,&before,sizeof schedule));
    puts("PASS transactional model/schedule rejection and owned bank pointers");return 0;
}
