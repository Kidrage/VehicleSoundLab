#include "atlas_drive/render.h"
#include "core/engine.h"
#include "drive/scenarios.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do { if(!(x)){fprintf(stderr,"body check line%d: %s\n",__LINE__,#x);return 1;} } while(0)
static SdProfile profile;
static SaBank bank;
static SaVoice plain,tapped,saved;
static AdRender baseline,layered,surround;
static VslEngine ea,eb,ec;
static float out[240*12],a_raw[480],b_raw[480],c_raw[480],low[480],low_surround[480];
static float objects[240*VSL_OBJECTS],body_objects[240*VSL_OBJECTS];

int main(void) {
    HbBand band=hb_band_default(),bad=band;
    const SdProfile *profiles[]={&profile};
    HbMix mix;
    double full[2],tap[2],old[2],dna[2],body[2],body_energy=0,unity_error=0,analytic_error=0;
    unsigned n,c,h,block;
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={{0},{.25,1,0,.7,0,0,0,0}},enabled,multichannel;
    AdCapture ca={0},cb={0},cc={0};
    VslParams p=vsl_default_params(VSL_V10);
    CHECK(hb_band_valid(&band));bad.stop_high=NAN;CHECK(!hb_band_valid(&bad));
    CHECK(hb_band_weight(&band,0)==0&&hb_band_weight(&band,20)==0&&hb_band_weight(&band,350)==0);
    CHECK(hb_band_weight(&band,35)==1&&hb_band_weight(&band,180)==1);
    for(n=0;n<10000;++n){double w=hb_band_weight(&band,n*.1);CHECK(w>=0&&w<=1);}
    profile.rate=48000;profile.window=1024;profile.hop=256;profile.harmonics=8;profile.base_hz=60;
    for(h=0;h<8;++h)for(c=0;c<2;++c){
        double phase=.31*h+.2*c,amp=.09/(h+1);
        profile.harmonic[h].mean[2*c]=amp*cos(phase);
        profile.harmonic[h].mean[2*c+1]=amp*sin(phase);
    }
    CHECK(sa_bank_init(&bank,profiles,1,0));
    CHECK(sa_voice_init(&plain,&bank,48271,60,0,.7)&&sa_voice_init(&tapped,&bank,48271,60,0,.7));
    for(n=0;n<20000;++n){
        double phase=tapped.phase;
        sa_voice_tick(&plain,old);CHECK(sa_voice_tick_body(&tapped,&band,full,tap));
        CHECK(!memcmp(full,old,sizeof full)&&!memcmp(&plain,&tapped,sizeof plain));
        for(c=0;c<2;++c){
            double expected=0;
            for(h=0;h<8;++h)expected+=hb_band_weight(&band,60*(h+1))*.7*.09/(h+1)*cos((h+1)*phase+.31*h+.2*c);
            analytic_error=fmax(analytic_error,fabs(tap[c]-expected));
        }
    }
    CHECK(analytic_error<2e-12);
    saved=tapped;CHECK(!sa_voice_tick_body(&tapped,&bad,full,tap)&&!memcmp(&saved,&tapped,sizeof saved));
    CHECK(hb_mix_init(&mix,48000,.6,1));mix.envelope=.73;
    for(n=0;n<10000;++n){
        CHECK(sa_voice_tick_body(&tapped,&band,full,tap));
        hb_mix_tick(&mix,full,tap,.73,.73,dna,body);
        for(c=0;c<2;++c)unity_error=fmax(unity_error,fabs(dna[c]+body[c]-.73*full[c]));
    }
    CHECK(unity_error<1e-15);
    CHECK(!hb_mix_set(&mix,NAN)&&mix.target==.6);
    CHECK(hb_mix_set(&mix,0));
    for(n=0;n<48000;++n)hb_mix_tick(&mix,full,tap,.73,.5,dna,body);
    CHECK(mix.amount==0&&body[0]==0&&body[1]==0&&dna[0]==full[0]*.73);
    CHECK(!hb_mix_init(&mix,44100,0,1)&&!hb_mix_init(&mix,48000,-1,1));

    CHECK(ad_render_init(&baseline,&ea,&config,&control));
    enabled=control;enabled.mix.body_mix=1;
    CHECK(ad_render_init(&layered,&eb,&config,&enabled));
    config.channels=12;multichannel=enabled;multichannel.mix.spatial=1;multichannel.mix.room=.3;
    CHECK(ad_render_init(&surround,&ec,&config,&multichannel));
    ca.dna_raw=a_raw;cb.dna_raw=b_raw;cc.dna_raw=c_raw;
    cb.body=low;cc.body=low_surround;cb.objects=objects;cb.body_objects=body_objects;
    for(block=0;block<1800;++block){
        vsl_scenario_apply(VSL_SCENARIO_AUTO,block*.005,&p);
        control.drive.mode=p.drive_mode;control.drive.ignition=p.ignition;control.drive.start_id=p.start_id;
        control.drive.gear=p.gear;control.drive.automatic=p.auto_gear;control.drive.backfire=p.backfire;
        control.drive.rpm=p.rpm;control.drive.load=p.load;control.drive.throttle=p.throttle;control.drive.brake=p.brake;
        enabled=control;enabled.mix.body_mix=block<1400?1:0;
        multichannel=enabled;multichannel.mix.spatial=1;multichannel.mix.room=.3;
        CHECK(ad_render_set(&baseline,&control)&&ad_render_set(&layered,&enabled)&&ad_render_set(&surround,&multichannel));
        CHECK(ad_render_process(&baseline,out,240,&ca)&&ad_render_process(&layered,out,240,&cb));
        CHECK(ad_render_process(&surround,out,240,&cc));
        CHECK(!memcmp(&ea.drive,&eb.drive,sizeof ea.drive)&&!memcmp(&eb.drive,&ec.drive,sizeof eb.drive));
        CHECK(!memcmp(a_raw,b_raw,sizeof a_raw)&&!memcmp(a_raw,c_raw,sizeof a_raw));
        CHECK(!memcmp(low,low_surround,sizeof low));
        CHECK(!memcmp(&baseline.dna,&layered.dna,sizeof baseline.dna));
        for(n=0;n<240;++n){
            CHECK(objects[n*VSL_OBJECTS+VSL_BODY]==body_objects[n*VSL_OBJECTS+VSL_BODY]);
            CHECK(body_objects[n*VSL_OBJECTS+VSL_EXHAUST_L]==0);
            body_energy+=low[n*2]*low[n*2]+low[n*2+1]*low[n*2+1];
        }
    }
    CHECK(body_energy>.01&&eb.drive.shift_events>=1&&layered.body.amount==0);
    enabled.mix.body_mix=NAN;CHECK(!ad_render_set(&layered,&enabled)&&layered.target.mix.body_mix==0);
    CHECK(ea.pad.phase[0]==0&&eb.pad.phase[0]==0);
    printf("body analytic error%.3g unity error%.3g energy%.4g; shared clock/RNG, controller and2/12channel sources passed\n",
        analytic_error,unity_error,body_energy);return 0;
}
