#include "vehicle_source/internal.h"
#include "core/engine.h"
#include "../catalog_drive_v1/models.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"unified DNA check line %d: %s\n",__LINE__,#x);goto done;}}while(0)
static float full[480*2],split[480*2],line[480*2],air[480*2];
int main(void) {
    DcPreset *p=NULL;VsAssets *assets=NULL;VsEngine *a=NULL,*b=NULL;VsControl c,bad;
    VsOutput out={0},part={0};VslSpatial *space=NULL;unsigned block,j;float le=0,ae=0;int result=1;
    DchVoice *v=NULL;DchControl control=dch_default();DchFrame f;float one[2]={.2f,-.1f},two[2]={.03f,.04f};
    DchContext context={0,1000,850,1};
    /* Independent analytical check of every response row, with no fingerprint
       and constant known inputs. A zero state multiplier must silence its bus. */
    for(j=0;j<DCH_STATES;++j){
        unsigned n;control=dch_default();control.line_state[j]=0;control.air_state[j]=.5f;context.state=j;
        CHECK(v=dch_create(NULL,731,&control));
        for(n=0;n<144000;++n)CHECK(dch_tick(v,&context,one,two,&f));
        CHECK(fabsf(f.line[0])<1e-14f&&fabsf(f.air[0]-.015f)<(2*FLT_EPSILON*.015f/(1-expf(-1/(.080f*48000)))));
        dch_destroy(v);v=NULL;
    }
    CHECK(p=cd_models_load(DC_FINE_IDLE));CHECK(assets=vs_assets_from_atlas(dc_preset_config(p)));
    {AdControl old=dc_preset_initial(p);vs_control_from_atlas(&old,&c);}
    dc_preset_destroy(p);p=NULL;c.dna_unified=1;c.mode=VS_BENCH;c.ignition=c.start_id=1;
    c.intake_gain=c.air_gain=c.road_gain=c.wind_gain=0;
    CHECK(a=vs_engine_create(assets,&c));CHECK(b=vs_engine_create(assets,&c));
    CHECK(space=malloc(sizeof *space));memcpy(space,&a->owner.spatial,sizeof *space);
    out.monitor=full;out.stem[VS_DNA]=line;out.stem[VS_DETAIL]=air;
    for(block=0;block<450;++block){
        if(block==150)c.rpm=4000;if(block==250)c.rpm=9500;if(block==350)c.ignition=0;
        CHECK(vs_engine_set(a,&c)&&vs_engine_set(b,&c));CHECK(vs_engine_process(a,&out,480));
        for(j=0;j<480;){unsigned n=480-j>73?73:480-j;part.monitor=split+2*j;CHECK(vs_engine_process(b,&part,n));j+=n;}
        CHECK(!memcmp(full,split,sizeof full));CHECK(!memcmp(space,&a->owner.spatial,sizeof *space));
        for(j=0;j<960;++j){CHECK(isfinite(full[j]));le+=line[j]*line[j];ae+=air[j]*air[j];}
    }
    CHECK(le>0&&ae>0);
    bad=c;bad.dna.air=NAN;CHECK(!vs_engine_set(a,&bad));bad=c;bad.dna.air_state[5]=2.61f;CHECK(!vs_engine_set(a,&bad));
    bad=c;bad.dna_unified=0;CHECK(!vs_engine_set(a,&bad));
    puts("PASS: six response rows, owned fingerprint, exact partitioning, unchanged spatial storage, finite startup-to-high-RPM-to-stop, invalid controls");result=0;
done:dch_destroy(v);dc_preset_destroy(p);vs_engine_destroy(a);vs_engine_destroy(b);vs_assets_destroy(assets);free(space);return result;
}
