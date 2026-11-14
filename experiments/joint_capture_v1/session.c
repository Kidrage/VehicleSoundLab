#define _CRT_SECURE_NO_WARNINGS
#include "session.h"
#include "../catalog_drive_v1/models.h"
#include "atlas_take/player.h"
#include "io/file.h"
#include "io/wav.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define JC_FRAMES 240000u
#define JC_WARMUP 96000u
#define CHECK(x) do{if(!(x)){fprintf(stderr,"joint_capture%d: %s\n",__LINE__,#x);goto done;}}while(0)
static void capture(AtPlayer *b,AdCapture *c) {
    memset(c,0,sizeof *c);
    c->dna_raw=b->raw;c->dna=b->dna;c->residual=b->residual;c->body=b->body;
    c->events=b->events;c->aux_objects=b->auxiliary;c->startup=b->startup;c->catch_bloom=b->catch_bloom;
    c->resonant=b->resonant;c->coherent_low_raw=b->coherent_low_raw;c->coherent_low=b->coherent_low;
}
int jc_record(int selection,uint64_t seed,AtTake *t) {
    DcPreset *preset=NULL;AmRender *r=NULL;VslEngine *e=NULL;AtPlayer *scratch=NULL;
    AdConfig cfg;AdControl c;AdCapture cap;float out[480];unsigned at;double low,high;
    uint64_t ah=AT_HASH_INITIAL,sh=AT_HASH_INITIAL;int ok=0;
    if(!t||t->events||!seed||!(selection==DC_WARM||selection==DC_HOLLOW||selection==DC_F3||
        selection==DC_F3_FIRST_LOCAL||selection==DC_F3_SECOND_LOCAL))return 0;
    preset=cd_models_load(selection);CHECK(preset);
    cfg=*dc_preset_config(preset);cfg.seed=seed;cfg.channels=2;
    CHECK(!cfg.fine_idle_profile&&!cfg.idle_profile&&!cfg.startup_profile&&!cfg.catch_profile&&!cfg.source_processor);
    low=cfg.bank->profile[0]->base_hz;high=cfg.bank->profile[cfg.bank->count-1]->base_hz;
    c=dc_preset_initial(preset);c.drive.mode=VSL_BENCH;c.drive.ignition=c.drive.start_id=1;
    c.drive.gear=5;c.drive.automatic=c.drive.backfire=0;c.drive.load=.8;c.drive.rpm=low/cfg.root_per_rpm;
    c.mix.gain=c.mix.detail=c.mix.width=1;c.mix.event_gain=c.mix.room=0;
    c.mix.spatial=c.mix.propagation=0;c.mix.perspective=0;
    CHECK(at_take_allocate(t,1001)&&at_take_begin(t,&cfg,&c));
    cfg=t->assets->config;dc_preset_destroy(preset);preset=NULL;
    r=calloc(1,sizeof *r);e=calloc(1,sizeof *e);scratch=calloc(1,sizeof *scratch);
    CHECK(r&&e&&scratch);capture(scratch,&cap);
    CHECK(am_render_init(r,e,&cfg,&c));
    for(at=0;at<JC_FRAMES;at+=240) {
        double u=at<JC_WARMUP?0:(at-JC_WARMUP)/(double)(JC_FRAMES-JC_WARMUP-240);
        c.drive.rpm=(low+(high-low)*u)/cfg.root_per_rpm;
        CHECK(at_take_event(t,at,&c)&&am_render_set(r,&c)&&am_render_process(r,out,240,0,&cap));
        ah=at_hash_samples(ah,out,480);sh=at_hash_sources(sh,&cap,240);
        CHECK(at_take_commit(t,240,ah,sh));
    }
    at_take_finish(t);CHECK(at_take_valid(t));ok=1;
done:if(r)am_render_dispose(r);free(r);free(e);free(scratch);dc_preset_destroy(preset);
    if(!ok)at_take_free(t);return ok;
}
static int available(const char *path) {FILE *f=vsl_fopen(path,"rb");if(!f)return 1;fclose(f);return 0;}
int jc_export(const AtTake *t,const char *prefix,unsigned block,int channels) {
    const char *suffix[]={"_out.wav","_layers.wav",".csv",".json","_raw.wav","_envelope.f64"};char path[6][4096];
    VslWavWriter wave={0},stems={0},raw={0};FILE *csv=NULL,*json=NULL,*envelope=NULL;
    AtPlayer *p=NULL;VslEngine *e=NULL;float out[512*12],layers[512*LM_SAMPLES];AdTelemetry telemetry[512];
    unsigned n;int ok=0;double max_sum_error=0,envelopes[512];const uint16_t endian=1;
    if(!t||!prefix||!block||block>512||(channels!=2&&channels!=12))return 0;
    if(*(const unsigned char*)&endian!=1)return 0;
    for(int i=0;i<6;++i){int size=snprintf(path[i],sizeof path[i],"%s%s",prefix,suffix[i]);
        if(size<0||size>=(int)sizeof path[i]||!available(path[i]))return 0;}
    p=calloc(1,sizeof *p);e=calloc(1,sizeof *e);CHECK(p&&e&&at_player_init(p,e,t,channels));
    CHECK(vsl_wav_begin_float(&wave,path[0],48000,channels)&&vsl_wav_begin_float(&stems,path[1],48000,LM_SAMPLES));
    CHECK(vsl_wav_begin_float(&raw,path[4],48000,2));
    csv=vsl_fopen(path[2],"wb");envelope=vsl_fopen(path[5],"wb");CHECK(csv&&envelope);
    fputs("frame,rpm,root_hz,load,envelope,lower,upper,blend,coverage,lifecycle,operating,resonant_support,resonant_gain\n",csv);
    while(!at_player_complete(p)) {
        /* One underlying render call so the public raw scratch buffer covers
           all returned frames. The generic player may otherwise split a
           request at several events and retain only its last raw sub-block. */
        uint64_t at=p->render.frame,next=t->frames;unsigned event=p->next,request=block;
        while(event<t->count&&t->events[event].frame<=at)++event;
        if(event<t->count)next=t->events[event].frame;
        if(at<t->stop_frame&&t->stop_frame<next)next=t->stop_frame;
        if(next-at<request)request=(unsigned)(next-at);
        CHECK(request);n=at_player_process_layers(p,out,request,telemetry,layers);CHECK(n==request);
        CHECK(vsl_wav_write(&wave,out,n)&&vsl_wav_write(&stems,layers,n)&&vsl_wav_write(&raw,p->raw,n));
        for(unsigned j=0;j<n;++j) {
            const AdTelemetry *a=telemetry+j;
            envelopes[j]=a->envelope;
            if(a->frame%240==0||a->frame+1==t->frames)
                fprintf(csv,"%llu,%.17g,%.17g,%.17g,%.17g,%u,%u,%.17g,%d,%d,%d,%.17g,%.17g\n",
                    (unsigned long long)a->frame,a->rpm,a->root_hz,a->load,a->envelope,a->lower,a->upper,a->blend,
                    a->coverage,a->lifecycle,a->operating,a->resonant_support,a->resonant_gain);
            for(unsigned k=0;k<LM_SAMPLES;++k)CHECK(isfinite(layers[j*LM_SAMPLES+k]));
            for(int k=0;k<channels;++k)CHECK(isfinite(out[j*channels+k]));
            if(channels==2&&p->current.mix.spatial==0)for(unsigned c=0;c<2;++c) {
                double sum=0;for(unsigned k=0;k<LM_LAYERS;++k)sum+=layers[j*LM_SAMPLES+2*k+c];
                max_sum_error=fmax(max_sum_error,fabs(sum-out[2*j+c]));
            }
        }
        CHECK(fwrite(envelopes,sizeof(double),n,envelope)==n);
    }
    CHECK(at_player_verified(p)&&!ferror(csv)&&!ferror(envelope));
    CHECK(vsl_wav_end(&wave)&&vsl_wav_end(&stems)&&vsl_wav_end(&raw));
    json=vsl_fopen(path[3],"wb");CHECK(json);
    fprintf(json,"{\"protocol\":\"vsl.joint-capture/2\",\"frames\":%llu,\"channels\":%d,\"block\":%u,\"verified\":true,\"audio_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"render_id\":\"%s\",\"max_dry_bus_sum_error_FS\":%.17g,\"envelope_encoding\":\"IEEE754-little-endian-f64\",\"dry_bus_order\":[\"DNA\",\"LOW\",\"DETAIL\",\"AUX\",\"EVENT\",\"OTHER\"]}\n",
        (unsigned long long)t->frames,channels,block,(unsigned long long)p->audio_hash,(unsigned long long)p->source_hash,at_render_id(),max_sum_error);
    CHECK(!ferror(json));ok=1;
done:if(wave.file&&!vsl_wav_end(&wave))ok=0;if(stems.file&&!vsl_wav_end(&stems))ok=0;
    if(raw.file&&!vsl_wav_end(&raw))ok=0;
    if(csv&&fclose(csv))ok=0;if(json&&fclose(json))ok=0;if(envelope&&fclose(envelope))ok=0;
    if(p)at_player_dispose(p);free(p);free(e);return ok;
}
