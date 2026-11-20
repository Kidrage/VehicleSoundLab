#define _CRT_SECURE_NO_WARNINGS
#include "engine.h"
#include "modules.h"
#include "io/file.h"
#include "profiles/firing.h"
#include "exhaust_spectrum.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static float bell(float f, float center, float width) {
    float d = logf(f / center) / width;
    return expf(-.5f * d * d);
}
void vsl_dna_update(VslEngine *e) {
    const VslProfile *p = vsl_profile(e->smooth.profile);
    float cycle_hz = e->control.rpm / 120.0f;
    float energy = 0;
    int k, c;
    for (k = 1; k <= VSL_PARTIALS; ++k) {
        float f = cycle_hz * k, re = 0, im = 0,rr=0,ri=0;
        float envelope, cutoff;
        if (e->dna.custom_count) {
            /* A user DNA is a separate pitch law, unrelated to cylinder firing. */
            float ratio = e->control.rpm / 3000.0f;
            f = e->dna.custom_root * ratio * k;
            if (k <= e->dna.custom_count) {
                re = cosf(e->dna.custom_phase[k-1]) * e->dna.custom_amp[k-1];
                im = sinf(e->dna.custom_phase[k-1]) * e->dna.custom_amp[k-1];
            }
            rr=re;ri=im;
        } else if (e->smooth.profile == VSL_SCIFI) {
            envelope = powf((float)k, -.95f) *
                (.18f + bell(f, 180, .6f) + .8f*bell(f, 900+e->control.load*450, .4f));
            if (k % 3 == 0 || k == 2 || k == 5) {
                re = envelope * cosf(.35f*k);
                im = envelope * sinf(.35f*k);
            }
            rr=re;ri=im;
        } else {
            /* Fourier coefficients of a 720-degree combustion cycle. Bank delay
               changes phase in seconds, rather than arbitrarily detuning orders. */
            for (c = 0; c < p->cylinders; ++c) {
                float cycle_position=e->smooth.profile==VSL_V10?
                    vsl_firing_degrees(e->smooth.profile,c,p->cylinders)/720.0f:(float)c/p->cylinders;
                float angle = 2*VSL_PI*(cycle_position +
                    (p->bank[c] ? cycle_hz*p->bank_delay : 0));
                float weight = 2*(1 + .045f*sinf(1.7f*c)) / p->cylinders;
                if(p->bank[c]) { rr+=weight*cosf(k*angle);ri-=weight*sinf(k*angle); }
                else { re+=weight*cosf(k*angle);im-=weight*sinf(k*angle); }
            }
            envelope = vsl_exhaust_envelope(e,(float)k,f);
            re *= envelope; im *= envelope;rr*=envelope;ri*=envelope;
        }
        cutoff = vsl_clamp((.475f*e->sample_rate-f*e->combustion.stretch)/(.035f*e->sample_rate),0,1);
        re *= cutoff; im *= cutoff;rr*=cutoff;ri*=cutoff;
        e->dna.target_real[k-1] = re;
        e->dna.target_imag[k-1] = im;
        e->dna.target_right_real[k-1]=rr;e->dna.target_right_imag[k-1]=ri;
        energy += .5f*(re*re + im*im+rr*rr+ri*ri);
    }
    /* Stable loudness leaves load dynamics to the explicit envelope. */
    energy = .36f / sqrtf(fmaxf(energy, .00001f));
    e->dna.factory_scale=energy;
    for (k=0;k<VSL_PARTIALS;++k) {
        e->dna.target_real[k] *= energy;
        e->dna.target_imag[k] *= energy;
        e->dna.target_right_real[k]*=energy;e->dna.target_right_imag[k]*=energy;
    }
}
void vsl_dna_tick(VslEngine *e,float *left,float *right) {
    float phase = e->dna.custom_count?e->dna.pitch_phase:e->control.phase;
    int varied=e->combustion.mix>0&&!e->dna.custom_count&&e->smooth.profile==VSL_V10;
    float right_phase=phase+(varied?e->combustion.phase_delta[1]:0);
    float s,c,sk,ck,sr,cr,skr,ckr,output=0,r=0;
    float slew = 1-expf(-1/(.008f*e->sample_rate));
    int k;
    if(varied)phase+=e->combustion.phase_delta[0];
    s=sinf(phase);c=cosf(phase);sk=s;ck=c;
    sr=sinf(right_phase);cr=cosf(right_phase);skr=sr;ckr=cr;
    for (k=0;k<VSL_PARTIALS;++k) {
        float next;
        e->dna.real[k] += slew*(e->dna.target_real[k]-e->dna.real[k]);
        e->dna.imag[k] += slew*(e->dna.target_imag[k]-e->dna.imag[k]);
        e->dna.right_real[k]+=slew*(e->dna.target_right_real[k]-e->dna.right_real[k]);
        e->dna.right_imag[k]+=slew*(e->dna.target_right_imag[k]-e->dna.right_imag[k]);
        output += e->dna.real[k]*ck - e->dna.imag[k]*sk;
        r+=e->dna.right_real[k]*(varied?ckr:ck)-e->dna.right_imag[k]*(varied?skr:sk);
        next = sk*c+ck*s; ck = ck*c-sk*s; sk = next;
        if(varied) { next=skr*cr+ckr*sr;ckr=ckr*cr-skr*sr;skr=next; }
    }
    {
        float variation=e->dna.custom_count?1:1+e->smooth.irregularity*(.07f*e->voice.idle*sinf(e->detail.variation_phase)+.025f*sinf(phase*2.0f));
        if(varied) {
            /* Replace the old forced opposite AM with independent bounded
               pressure-event variation. Mean crank phase is unchanged. */
            float mix=e->combustion.mix;
            *left=output*e->voice.dna_gain*(1+(variation-1)*(1-mix))*e->combustion.gain[0];
            *right=r*e->voice.dna_gain*(1+(1-variation)*(1-mix))*e->combustion.gain[1];
        } else {
            *left=output*e->voice.dna_gain*variation;
            *right=r*e->voice.dna_gain*(2-variation);
        }
    }
}
int vsl_load_dna(VslEngine *e, const char *path) {
    FILE *f = vsl_fopen(path,"r");
    char tag[24]; int version,n,i; float root,amp[VSL_PARTIALS],phase[VSL_PARTIALS];
    if (!f) return 0;
    if (fscanf(f,"%23s %d %f %d",tag,&version,&root,&n)!=4 ||
        strcmp(tag,"VSL_DNA") || version!=1 || n<1 || n>VSL_PARTIALS ||
        !isfinite(root) || root<10 || root>4000) { fclose(f); return 0; }
    for(i=0;i<n;++i) {
        if(fscanf(f,"%f %f",&amp[i],&phase[i])!=2 || !isfinite(amp[i]) ||
           !isfinite(phase[i]) || amp[i]<0 || amp[i]>100) { fclose(f); return 0; }
    }
    fclose(f);
    memcpy(e->dna.custom_amp,amp,(size_t)n*sizeof(float));
    memcpy(e->dna.custom_phase,phase,(size_t)n*sizeof(float));
    e->dna.custom_count=n; e->dna.custom_root=root;e->dna.pitch_phase=0;
    return 1;
}
