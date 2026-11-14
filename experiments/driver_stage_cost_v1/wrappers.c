#include "timing.h"
#include "dna_atlas/voice.h"
#include "drive_recipe/voice.h"
#include "drive_resonance/voice.h"
#include "fine_idle_layer/state.h"
#include "residual_atlas/voice.h"
#include "drive_aux/voice.h"
#include "harmonic_body/mix.h"
#include "spatial/scene.h"
#include "drive/drive.h"
#include "core/modules.h"
#include <windows.h>
#include <string.h>
SpMetric sp_metrics[SP_COUNT];
const char *sp_names[SP_COUNT]={"main_OSC","power_shape","coherent_low","resonant_detail","fixed_idle","residual","auxiliary","body_mix","spatial","drive_step","orchestrate","empty_timer"};
uint64_t sp_begin(void){LARGE_INTEGER n;QueryPerformanceCounter(&n);return (uint64_t)n.QuadPart;}
uint64_t sp_frequency(void){LARGE_INTEGER n;QueryPerformanceFrequency(&n);return (uint64_t)n.QuadPart;}
void sp_end(unsigned stage,uint64_t before){uint64_t n=sp_begin();++sp_metrics[stage].calls;sp_metrics[stage].ticks+=n-before;}
void sp_reset(void){memset(sp_metrics,0,sizeof sp_metrics);}
int sp_sa_voice_tick_body(SaVoice *s,const HbBand *b,double *x,double *body){uint64_t t=sp_begin();int ok=sa_voice_tick_body(s,b,x,body);sp_end(SP_MAIN,t);return ok;}
int sp_sa_voice_tick_shaped_body(SaVoice *s,const HbBand *b,const double *g,double a,double *x,double *body){uint64_t t=sp_begin();int ok=sa_voice_tick_shaped_body(s,b,g,a,x,body);sp_end(SP_MAIN,t);return ok;}
int sp_drc_shape(const DrcBank *b,const SaVoice *s,const DrsVoice *d,double *g){uint64_t t=sp_begin();int ok=drc_shape(b,s,d,g);sp_end(SP_SHAPE,t);return ok;}
int sp_drc_voice_tick(DrcVoice *s,const SaVoice *dna,double p,DrcFrame *f){uint64_t t=sp_begin();int ok=drc_voice_tick(s,dna,p,f);sp_end(SP_LOW,t);return ok;}
int sp_drs_voice_tick(DrsVoice *s,const SaVoice *dna,double p,DrsFrame *f){uint64_t t=sp_begin();int ok=drs_voice_tick(s,dna,p,f);sp_end(SP_RESONANCE,t);return ok;}
int sp_fi_state_tick(FiState *s,int gate,double amount,double motion,double detail,double env,FiFrame *f){uint64_t t=sp_begin();int ok=fi_state_tick(s,gate,amount,motion,detail,env,f);sp_end(SP_IDLE,t);return ok;}
void sp_ra_voice_tick(RaVoice *s,double *x,double *raw){uint64_t t=sp_begin();ra_voice_tick(s,x,raw);sp_end(SP_RESIDUAL,t);}
void sp_da_voice_tick(DaVoice *s,VslEngine *e,VslObjectFrame *raw,VslObjectFrame *mixed){uint64_t t=sp_begin();da_voice_tick(s,e,raw,mixed);sp_end(SP_AUX,t);}
void sp_hb_mix_tick(HbMix *s,const double *full,const double *low,double de,double be,double *d,double *b){uint64_t t=sp_begin();hb_mix_tick(s,full,low,de,be,d,b);sp_end(SP_BODY,t);}
void sp_vsl_scene_tick(VslEngine *e,const VslObjectFrame *o,double *x,int n){uint64_t t=sp_begin();vsl_scene_tick(e,o,x,n);sp_end(SP_SPATIAL,t);}
void sp_vsl_drive_step(VslDrive *d,const VslParams *p,double dt){uint64_t t=sp_begin();vsl_drive_step(d,p,dt);sp_end(SP_DRIVE,t);}
void sp_vsl_orchestrate(VslEngine *e,double dt){uint64_t t=sp_begin();vsl_orchestrate(e,dt);sp_end(SP_ORCHESTRATE,t);}
