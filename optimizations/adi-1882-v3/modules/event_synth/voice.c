#include "internal.h"
#include <math.h>
#include <string.h>
void es_voice_begin(EsVoice *v,const EsProfile *p,const EsRequest *r) {
    unsigned k;float variation;
    memset(v,0,sizeof *v);v->profile=*p;v->request=*r;v->active=1;
    v->rng=r->seed?r->seed:UINT32_C(0x97bd5821);
    /* One small event-wide offset, not independent detuned saw-like carriers. */
    variation=1+.002f*es_random(&v->rng);
    v->duration=(uint64_t)ceilf(p->duration_seconds*r->decay*ES_RATE);
    v->release_at=UINT64_MAX;v->end_reason=ES_NATURAL;
    for(k=0;k<p->mode_count;++k) {
        es_oscillator_init(v->modes+k,p->modes+k,r,variation);
        v->mode_contour[k]=es_contour_index(p,p->modes[k].hz);
        if(p->sweep_seconds>0)v->modes[k].sweep_step=(v->modes[k].end_hz-v->modes[k].frequency)/(ES_RATE*p->sweep_seconds*r->decay);
    }
    for(k=0;k<p->band_count;++k) {
        es_noise_init(v->bands+k,p->bands+k,r);
        v->band_contour[k]=es_contour_index(p,p->bands[k].hz);
        if(v->band_contour[k])v->bands[k].attack=0;
    }
    if(p->noise_lowpass_hz>0)es_color_init(v->noise_color,fminf(21000,p->noise_lowpass_hz*r->pitch));
}
int es_voice_finished(const EsVoice *v) {
    return v->age>=v->duration||(v->release_at!=UINT64_MAX&&v->age-v->release_at>=v->release_frames);
}
float es_voice_tick(EsVoice *v) {
    float x=0,noise=es_random(&v->rng),env=es_attack(v->age,v->profile.attack_seconds),ending;
    unsigned k;
    float contour[ES_CONTOURS];
    for(k=0;k<ES_CONTOURS;++k)if(v->profile.contours[k].count)
        contour[k]=es_contour_gain(v->profile.contours+k,(float)v->age/(ES_RATE*v->request.decay));
    for(k=0;k<v->profile.mode_count;++k) {
        EsOscillator *o=v->modes+k;
        float modal=es_oscillator_tick(o);
        if(v->mode_contour[k])modal*=contour[v->mode_contour[k]-1];
        else if(v->profile.modes[k].attack_seconds>0)
            modal*=es_attack(v->age,v->profile.modes[k].attack_seconds);
        x+=modal;
        if(!v->profile.gated&&!v->mode_contour[k])o->amplitude*=o->decay;
        if(v->profile.sweep_seconds>0&&v->age<ES_RATE*v->profile.sweep_seconds*v->request.decay)o->frequency+=o->sweep_step;
    }
    if(v->profile.noise_lowpass_hz>0) {
        float texture=0;
        for(k=0;k<v->profile.band_count;++k) {
            unsigned group=v->band_contour[k];
            float band=es_noise_tick(v->bands+k,noise,v->age,v->profile.gated||group);
            if(group)band*=contour[group-1];
            texture+=band;
        }
        x+=es_color_tick(v->noise_color,texture);
    } else {
        /* Preserve the original addition order and numeric path exactly. */
        for(k=0;k<v->profile.band_count;++k) {
            unsigned group=v->band_contour[k];
            float band=es_noise_tick(v->bands+k,noise,v->age,v->profile.gated||group);
            if(group)band*=contour[group-1];
            x+=band;
        }
    }
    /* Natural completion also fades to zero; no truncation of modal/noise tails. */
    ending=(float)(v->duration-v->age)/(ES_RATE*v->profile.release_seconds);
    if(ending<1)env*=ending*ending*(3-2*ending);
    if(v->release_at!=UINT64_MAX) {
        float remaining=1-(float)(v->age-v->release_at)/v->release_frames;
        env*=remaining*remaining*(3-2*remaining);
    }
    ++v->age;
    return x*env*v->profile.level*v->request.strength;
}
