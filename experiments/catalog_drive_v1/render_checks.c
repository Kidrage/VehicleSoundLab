#define _CRT_SECURE_NO_WARNINGS
#include "models.h"
#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define FRAMES 192123u
#define CHECK(x) do{if(!(x)){fprintf(stderr,"catalog render%d: %s\n",__LINE__,#x);goto done;}}while(0)
static AmRender small,wide;static VslEngine es,ew;static AtPlayer replay;
static float layers2[512*LM_SAMPLES],layers12[512*LM_SAMPLES];
static float raw[1024],dna[1024],body[1024],residual[1024],resonant[1024],lowraw[1024],low[1024];
static float aux[512*VSL_OBJECTS],events[512],startup[1024],catching[1024],idleraw[1024],idlesound[1024],core[1024],detail[1024];
static AdTelemetry telemetry[512];
static int run(const char *root,int selection) {
    DcPreset *preset=cd_models_load(selection);AtTake t={0},loaded={0};AdControl c,c12;AdConfig cfg,cfg12;AdCapture cap={0},cap12={0};
    float *reference=NULL,pcm[512*12];char path[4096];VslWavWriter wav={0};FILE *report=NULL;
    uint64_t ah=AT_HASH_INITIAL,sh=AT_HASH_INITIAL,wh=AT_HASH_INITIAL;unsigned at,n;double energy=0,peak=0;int ok=0;
    CHECK(preset);cfg=*dc_preset_config(preset);c=dc_preset_initial(preset);c.drive.ignition=c.drive.start_id=1;
    CHECK(at_take_allocate(&t,16)&&at_take_begin(&t,&cfg,&c));
    cfg=t.assets->config;dc_preset_destroy(preset);preset=NULL;
    cfg12=cfg;cfg12.channels=12;c12=c;c12.mix.spatial=1;
    CHECK(am_render_init(&small,&es,&cfg,&c)&&am_render_init(&wide,&ew,&cfg12,&c12));
    reference=calloc(FRAMES*2,sizeof(float));CHECK(reference);
    cap.dna_raw=raw;cap.dna=dna;cap.body=body;cap.residual=residual;cap.events=events;cap.aux_objects=aux;
    cap.startup=startup;cap.catch_bloom=catching;cap.resonant=resonant;cap.coherent_low_raw=lowraw;cap.coherent_low=low;
    if(cfg.fine_idle_profile){cap.idle_raw=idleraw;cap.idle=idlesound;cap.idle_modal=core;cap.idle_detail=detail;}
    cap.telemetry=telemetry;cap.layers=layers2;cap12=cap;cap12.layers=layers12;cap12.telemetry=NULL;
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at>257?257:FRAMES-at;
        const unsigned cuts[]={48000,96000,144000,FRAMES-480,FRAMES};
        for(unsigned j=0;j<5;++j)if(cuts[j]>at&&cuts[j]-at<n)n=cuts[j]-at;
        if(at==48000){c.drive.rpm=6500;c.drive.load=.7;}
        if(at==96000){c.drive.rpm=850;c.drive.load=-.6;}
        if(at==144000)c.drive.ignition=0;
        if(at==FRAMES-480)t.stop_frame=at;
        c12=c;c12.mix.spatial=1;
        CHECK(at_take_event(&t,at,&c)&&am_render_set(&small,&c)&&am_render_set(&wide,&c12));
        CHECK(am_render_process(&small,reference+2*at,n,at>=FRAMES-480,&cap));
        ah=at_hash_samples(ah,reference+2*at,n*2);sh=at_hash_sources(sh,&cap,n);
        CHECK(am_render_process(&wide,pcm,n,at>=FRAMES-480,&cap12));wh=at_hash_sources(wh,&cap12,n);
        CHECK(!memcmp(layers2,layers12,n*LM_SAMPLES*sizeof(float)));
        CHECK(!memcmp(&es.drive,&ew.drive,sizeof es.drive));
        CHECK(at_take_commit(&t,n,ah,sh));
        for(unsigned j=0;j<n*2;++j){float x=reference[2*at+j];CHECK(isfinite(x)&&fabs(x)<.95);energy+=(double)x*x;peak=fmax(peak,fabs(x));}
    }
    CHECK(energy>0&&sh==wh);am_render_dispose(&small);am_render_dispose(&wide);at_take_finish(&t);
    snprintf(path,sizeof path,"%s/voice_%d.vslrun",root,selection);CHECK(at_take_save(&t,path)&&at_take_load(&loaded,path));
    at_take_free(&t);CHECK(at_player_init(&replay,&es,&loaded,2));
    for(at=0;at<FRAMES;at+=n){n=FRAMES-at>347?347:FRAMES-at;CHECK(at_player_process(&replay,pcm,n,NULL)==n);CHECK(!memcmp(pcm,reference+2*at,n*2*sizeof(float)));}
    CHECK(at_player_verified(&replay));at_player_dispose(&replay);
    snprintf(path,sizeof path,"%s/voice_%d.wav",root,selection);CHECK(vsl_wav_begin_float(&wav,path,48000,2)&&vsl_wav_write(&wav,reference,FRAMES)&&vsl_wav_end(&wav));
    snprintf(path,sizeof path,"%s/voice_%d.json",root,selection);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"selection\":%d,\"key\":\"%s\",\"profile\":%d,\"root_per_rpm\":%.17g,\"frames\":%u,\"audio_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"render_id\":\"%s\",\"stems_2_12_exact\":true,\"driver_2_12_exact\":true,\"owned_replay_PCM_exact\":true,\"peak\":%.17g}\n",
        selection,dc_info(selection)->key,cfg.profile,cfg.root_per_rpm,FRAMES,(unsigned long long)ah,(unsigned long long)sh,at_render_id(),peak);
    ok=1;printf("PASS catalog voice%d same driver/stems2-12, owned replay exact, hash=%016llx\n",selection,(unsigned long long)ah);
done:
    if(report&&fclose(report))ok=0;if(wav.file)vsl_wav_end(&wav);free(reference);dc_preset_destroy(preset);
    am_render_dispose(&small);am_render_dispose(&wide);at_player_dispose(&replay);at_take_free(&t);at_take_free(&loaded);return ok;
}
int main(int argc,char **argv){if(argc!=2)return 2;for(int k=0;k<DC_COUNT;++k)if(!run(argv[1],k))return 3;return 0;}
