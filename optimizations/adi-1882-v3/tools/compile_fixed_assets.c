/* Offline authoring utility. Link against the full pre-compact vsl_core and
   run from the asset tree. Emits coefficients, never PCM or serialized pointers.
   %.9g with an explicit decimal point round-trips every finite IEEE FP32. */
#define _CRT_SECURE_NO_WARNINGS
#include "vehicle_source/internal.h"
#include "catalog_drive_v1/models.h"
#include <stdio.h>
#include <stdlib.h>

static void f(float x){printf("%#.9gf",(double)x);}
static void fs(const float *p,unsigned count){unsigned n;putchar('{');for(n=0;n<count;++n){if(n)putchar(',');if(n&&n%16==0)putchar('\n');f(p[n]);}putchar('}');}
static void sd(const SdProfile *p){
    unsigned h,k;
    printf("{.rate=%u,.window=%u,.hop=%u,.harmonics=%u,.components=%u,.base_hz=",p->rate,p->window,p->hop,p->harmonics,p->components);f(p->base_hz);
    printf(",.rho=");fs(p->rho,p->components);printf(",.harmonic={\n");
    for(h=0;h<p->harmonics;++h){const SdHarmonic *a=p->harmonic+h;if(h)printf(",\n");printf("{.mean=");fs(a->mean,4);printf(",.basis={");for(k=0;k<p->components;++k){if(k)putchar(',');fs(a->basis[k],4);}printf("},.rho=");f(a->rho);printf(",.root={");for(k=0;k<4;++k){if(k)putchar(',');fs(a->root[k],4);}printf("}}");}
    printf("}}");
}
static void bank(const SaBank *p){unsigned h;
    printf("{.profile={&fixed_assets.owned.profile[0]},.count=1,.harmonics=%u,.offset={",p->harmonics);f(p->offset[0]);printf("},.phase={{");
    for(h=0;h<p->harmonics;++h){if(h)putchar(',');fs(p->phase[0][h],2);}printf("}},.unit={{");
    for(h=0;h<p->harmonics;++h){if(h)putchar(',');fs(p->unit[0][h],4);}printf("}}\n#ifndef VSL_FIXED_V10\n,.sine=");fs(p->sine,SA_TABLE_SIZE+1);printf("\n#endif\n}");
}
static void rdt(const RdtProfile *p){unsigned b,j;
    printf("{.rate=%u,.count=%u,.warmup_frames=%u,.base_hz=",p->rate,p->count,p->warmup_frames);f(p->base_hz);printf(",.band={\n");
    for(b=0;b<p->count;++b){const RdtBand *v=p->band+b;if(b)printf(",\n");printf("{.order=%u,.sections=%u,.envelope_order=%u,.low_hz=",v->order,v->sections,v->envelope_order);f(v->low_hz);printf(",.high_hz=");f(v->high_hz);printf(",.sigma=");f(v->sigma);printf(",.gain=");f(v->gain);printf(",.right_over_left=");f(v->right_over_left);printf(",.a=");fs(v->a,v->order+1);printf(",.sos={");for(j=0;j<v->sections;++j){if(j)putchar(',');fs(v->sos[j],6);}printf("},.beta=");fs(v->beta,2*RDT_MAX_ENVELOPE);putchar('}');}
    printf("}}");
}
static void resonance(const DrsBank *p){
    printf("{.count=1,.enabled={%u},.kind={%u},.root={",p->enabled[0],p->kind[0]);f(p->root[0]);printf("},.outer_low=");f(p->outer_low);printf(",.inner_low=");f(p->inner_low);printf(",.inner_high=");f(p->inner_high);printf(",.outer_high=");f(p->outer_high);printf(",.profile={");rdt(&p->profile[0]);printf("}}");
}
static void recipe(const DrcBank *p,unsigned harmonics){
    printf("{.count=1,.has_low={%u},.root={",p->has_low[0]);f(p->root[0]);printf("},.scale={");f(p->scale[0]);printf("},.outer_low=");f(p->outer_low);printf(",.inner_low=");f(p->inner_low);printf(",.inner_high=");f(p->inner_high);printf(",.outer_high=");f(p->outer_high);printf(",.colour={{");f(p->colour[0].power_reduction);putchar(',');f(p->colour[0].low_hz);putchar(',');f(p->colour[0].high_hz);printf("}},.reduction={");fs(p->reduction[0],harmonics);printf("},.low={");sd(&p->low[0]);printf("}}");
}
static void ms(const MsProfile *p){unsigned k;printf("{.rate=%u,.count=%u,.mode={",p->rate,p->count);for(k=0;k<p->count;++k){const MsMode *m=p->mode+k;if(k)putchar(',');printf("{.hz=");f(m->hz);printf(",.amplitude=");fs(m->amplitude,2);printf(",.phase=");fs(m->phase,2);putchar('}');}printf("}}");}
static void mt(const MtProfile *p){unsigned k;printf("{.rate=%u,.count=%u,.hop_frames=%u,.alpha=",p->rate,p->count,p->hop_frames);f(p->alpha);printf(",.factor={");for(k=0;k<p->count;++k){if(k)putchar(',');fs(p->factor[k],p->count);}printf("}}");}
static void sf(const SfProfile *p){unsigned k;printf("{.rate=%u,.count=%u,.warmup_frames=%u,.band={",p->rate,p->count,p->warmup_frames);for(k=0;k<p->count;++k){const SfBand *b=p->band+k;if(k)putchar(',');printf("{.count=%u,.gain=",b->count);f(b->gain);printf(",.right_over_left=");f(b->right_over_left);printf(",.taps=");fs(b->taps,b->count);printf(",.decimation=%u}",b->decimation);}printf("}}");}
static void fi(const FiProfile *p){printf("{.modal=&fixed_assets.owned.fine_modal,.motion=&fixed_assets.owned.fine_motion,.detail=&fixed_assets.owned.fine_detail,.modal_ratio=");f(p->modal_ratio);printf(",.modal_gain=");f(p->modal_gain);printf(",.detail_gain=");f(p->detail_gain);printf(",.level_gain=");f(p->level_gain);printf(",.attack_frames=%u,.release_frames=%u}",p->attack_frames,p->release_frames);}
static void config(const AdConfig *p){printf("{.bank=&fixed_assets.owned.bank,.seed=UINT64_C(%llu),.profile=%d,.channels=%d,.root_per_rpm=",(unsigned long long)p->seed,p->profile,p->channels);f(p->root_per_rpm);printf(",.projection=%d,.route=%d,.scene_mode=%d,.resonant_bank=&fixed_assets.owned.resonant,.recipe_bank=&fixed_assets.owned.recipe,.fine_idle_profile=&fixed_assets.owned.fine_idle}",p->projection,p->route,p->scene_mode);}
static void control(const AdControl *p){
    printf("static const AdControl fixed_initial={.drive={.mode=%d,.ignition=%d,.start_id=%d,.gear=%d,.automatic=%d,.backfire=%d,.rpm=",p->drive.mode,p->drive.ignition,p->drive.start_id,p->drive.gear,p->drive.automatic,p->drive.backfire);f(p->drive.rpm);printf(",.load=");f(p->drive.load);printf(",.throttle=");f(p->drive.throttle);printf(",.brake=");f(p->drive.brake);printf("},.mix={");
#define FIELD(name) printf("." #name "=");f(p->mix.name);putchar(',')
    FIELD(gain);FIELD(detail);FIELD(event_gain);FIELD(width);FIELD(room);FIELD(perspective);
    printf(".spatial=%d,.propagation=%d,",p->mix.spatial,p->mix.propagation);
    FIELD(residual_gain);FIELD(body_mix);FIELD(intake_gain);FIELD(mechanical_gain);FIELD(air_gain);FIELD(road_gain);FIELD(wind_gain);FIELD(startup_gain);FIELD(catch_gain);FIELD(resonant_gain);FIELD(coherent_low_gain);FIELD(idle_mix);FIELD(idle_motion);FIELD(idle_detail);
#undef FIELD
    printf("}};\n");
}
int main(void){
    DcPreset *p=cd_models_load(0);VsAssets *a;AdControl c;const AtAssets *s;
    if(!p)return 1;a=vs_assets_from_atlas(dc_preset_config(p));c=dc_preset_initial(p);if(!a)return 2;s=&a->owned;
    if(s->bank.count!=1||s->profile[0].components!=12||s->resonant.kind[0]!=DRS_RDT||s->fine_detail.count!=2||s->config.residual_bank||s->config.startup_profile||s->config.catch_profile)return 3;
    printf("/* Generated by tools/compile_fixed_assets.c from original V3 FP32 loaders.\n   V10 one-anchor coefficients; no PCM, no addresses or runtime file loader. */\nstatic const VsAssets fixed_assets={.owned={\n.profile={");sd(s->profile);printf("},\n.bank=");bank(&s->bank);printf(",\n.config=");config(&s->config);printf(",\n.resonant=");resonance(&s->resonant);printf(",\n.recipe=");recipe(&s->recipe,s->bank.harmonics);printf(",\n.fine_modal=");ms(&s->fine_modal);printf(",\n.fine_motion=");mt(&s->fine_motion);printf(",\n.fine_detail=");sf(&s->fine_detail);printf(",\n.fine_idle=");fi(&s->fine_idle);printf("}};\n");control(&c);
    vs_assets_destroy(a);dc_preset_destroy(p);return ferror(stdout)?4:0;
}
