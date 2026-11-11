#define _CRT_SECURE_NO_WARNINGS
#include "dna_atlas/voice.h"
#include "osc_colour/profile.h"
#include "osc_colour/envelope.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do { if(!(x)){fprintf(stderr,"colour check line%d: %s\n",__LINE__,#x);return 1;} } while(0)
static SdProfile model;
static SaBank bank;
static SaVoice plain,shaped,other,saved;

static int parse(const char *text,OcProfile *p) {
    FILE *f=tmpfile();int ok;
    if(!f)return 0;
    if(fputs(text,f)<0||fseek(f,0,SEEK_SET)){fclose(f);return 0;}
    ok=oc_profile_read(f,p);if(fclose(f))ok=0;return ok;
}
int main(void) {
    const SdProfile *models[]={&model};
    OcProfile p={0},previous;OcEnvelope envelope,fragment;
    HbBand band=hb_band_default();
    double gain[OC_MAX_HARMONICS],full[2],body[2],baseline[2],discard[2],error=0,low_error=0;
    unsigned n,h,c;
    CHECK(parse("VSL_OSC_COLOUR 1 2\n1 -6.020599913279624\n8 12.041199826559248\n",&p));
    CHECK(oc_profile_compile(&p,gain,8));
    for(h=0;h<8;++h)CHECK(fabs(gain[h]-.5*(h+1))<1e-12);
    previous=p;
    CHECK(!parse("VSL_OSC_COLOUR 1 2\n2 0\n1 0\n",&p)&&!memcmp(&p,&previous,sizeof p));
    CHECK(!parse("VSL_OSC_COLOUR 2 2\n1 0\n8 0\n",&p));
    CHECK(!parse("VSL_OSC_COLOUR 1 2\n1 0\n8 nan\n",&p));
    CHECK(!parse("VSL_OSC_COLOUR 1 2\n1 0\n8 0\ntrailing",&p));
    CHECK(!parse("VSL_OSC_COLOUR 1 2\n1 0\n",&p));
    CHECK(!parse("VSL_OSC_COLOUR 1 17\n",&p));
    p.db[1]=24.1;gain[0]=-7;
    CHECK(!oc_profile_compile(&p,gain,8)&&gain[0]==-7);p=previous;
    CHECK(oc_profile_compile(&p,gain,8));
    CHECK(oc_envelope_init(&envelope,0,.12)&&oc_envelope_set(&envelope,1));
    fragment=envelope;
    CHECK(!oc_envelope_set(&envelope,NAN)&&envelope.target==1);
    CHECK(!oc_envelope_init(&envelope,0,.001)&&envelope.target==1);
    for(n=0;n<48000;++n){double before=envelope.amount;
        oc_envelope_tick(&envelope);CHECK(envelope.amount>=before&&envelope.amount<=1);
        CHECK(fabs(envelope.amount-(1-exp(-(n+1.)/(48000*.12))))<2e-13);
    }
    for(n=0;n<1000;++n){unsigned k;for(k=0;k<48;++k)oc_envelope_tick(&fragment);}
    CHECK(!memcmp(&envelope,&fragment,sizeof envelope));
    model.rate=48000;model.window=1024;model.hop=256;model.harmonics=8;model.base_hz=60;
    for(h=0;h<8;++h)for(c=0;c<2;++c){
        double phase=.31*h+.4*c,amp=.08/(h+1)*(c?.7:1);
        model.harmonic[h].mean[2*c]=amp*cos(phase);model.harmonic[h].mean[2*c+1]=amp*sin(phase);
    }
    CHECK(sa_bank_init(&bank,models,1,0));
    CHECK(sa_voice_init(&plain,&bank,48271,60,0,.7)&&sa_voice_init(&shaped,&bank,48271,60,0,.7));
    for(n=0;n<20000;++n){
        double phase=shaped.phase,amount=n<5000?0:.6;
        CHECK(sa_voice_tick_body(&plain,&band,baseline,discard));
        CHECK(sa_voice_tick_shaped_body(&shaped,&band,gain,amount,full,body));
        CHECK(!memcmp(&plain,&shaped,sizeof plain));
        if(!amount)CHECK(!memcmp(baseline,full,sizeof full));
        for(c=0;c<2;++c){
            double expected=0,lf=0;
            for(h=0;h<8;++h){
                double sample=.7*.08/(h+1)*(c?.7:1)*cos((h+1)*phase+.31*h+.4*c)*(1+amount*(gain[h]-1));
                expected+=sample;lf+=hb_band_weight(&band,60*(h+1))*sample;
            }
            error=fmax(error,fabs(full[c]-expected));low_error=fmax(low_error,fabs(body[c]-lf));
        }
    }
    CHECK(error<2e-12&&low_error<2e-12);
    saved=shaped;
    CHECK(!sa_voice_tick_shaped_body(&shaped,&band,gain,NAN,full,body)&&!memcmp(&saved,&shaped,sizeof saved));
    CHECK(!sa_voice_tick_shaped_body(&shaped,&band,gain,1.01,full,body)&&!memcmp(&saved,&shaped,sizeof saved));
    /* Stochastic stream, including muted/zero-shape paths, remains identical. */
    model.components=1;model.rho[0]=.6;model.harmonic[2].basis[0][0]=.01;
    model.harmonic[4].root[0][0]=.002;model.harmonic[4].rho=.3;
    CHECK(sa_voice_init(&plain,&bank,99,60,1,1)&&sa_voice_init(&shaped,&bank,99,60,1,1));
    other=plain;
    for(n=0;n<10000;++n){
        CHECK(sa_voice_tick_body(&plain,&band,baseline,discard));
        CHECK(sa_voice_tick_shaped_body(&shaped,&band,gain,.7,full,body));
        CHECK(sa_voice_tick_shaped_body(&other,&band,NULL,1,full,body));
        CHECK(!memcmp(baseline,full,sizeof full));
        CHECK(!memcmp(&plain,&shaped,sizeof plain)&&!memcmp(&plain,&other,sizeof plain));
    }
    printf("colour analytic max%.3g LF%.3g; exact bypass/state, common stereo phase, monotonic smoothing and transactional profiles passed\n",error,low_error);
    return 0;
}
