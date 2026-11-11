#define _CRT_SECURE_NO_WARNINGS
#include "engine.h"
#include "modules.h"
#include "io/file.h"
#include "profiles/firing.h"
#include "exhaust_spectrum.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

static double bell(double f, double center, double width) {
    double d = log(f / center) / width;
    return exp(-.5 * d * d);
}
void vsl_dna_update(VslEngine *e) {
    const VslProfile *p = vsl_profile(e->smooth.profile);
    double cycle_hz = e->control.rpm / 120.0;
    double energy = 0;
    int k, c;
    for (k = 1; k <= VSL_PARTIALS; ++k) {
        double f = cycle_hz * k, re = 0, im = 0,rr=0,ri=0;
        double envelope, cutoff;
        if (e->dna.custom_count) {
            /* A user DNA is a separate pitch law, unrelated to cylinder firing. */
            double ratio = e->control.rpm / 3000.0;
            f = e->dna.custom_root * ratio * k;
            if (k <= e->dna.custom_count) {
                re = cos(e->dna.custom_phase[k-1]) * e->dna.custom_amp[k-1];
                im = sin(e->dna.custom_phase[k-1]) * e->dna.custom_amp[k-1];
            }
            rr=re;ri=im;
        } else if (e->smooth.profile == VSL_SCIFI) {
            envelope = pow((double)k, -.95) *
                (.18 + bell(f, 180, .6) + .8*bell(f, 900+e->control.load*450, .4));
            if (k % 3 == 0 || k == 2 || k == 5) {
                re = envelope * cos(.35*k);
                im = envelope * sin(.35*k);
            }
            rr=re;ri=im;
        } else {
            /* Fourier coefficients of a 720-degree combustion cycle. Bank delay
               changes phase in seconds, rather than arbitrarily detuning orders. */
            for (c = 0; c < p->cylinders; ++c) {
                double cycle_position=e->smooth.profile==VSL_V10?
                    vsl_firing_degrees(e->smooth.profile,c,p->cylinders)/720.0:(double)c/p->cylinders;
                double angle = 2*VSL_PI*(cycle_position +
                    (p->bank[c] ? cycle_hz*p->bank_delay : 0));
                double weight = 2*(1 + .045*sin(1.7*c)) / p->cylinders;
                if(p->bank[c]) { rr+=weight*cos(k*angle);ri-=weight*sin(k*angle); }
                else { re+=weight*cos(k*angle);im-=weight*sin(k*angle); }
            }
            envelope = vsl_exhaust_envelope(e,(double)k,f);
            re *= envelope; im *= envelope;rr*=envelope;ri*=envelope;
        }
        cutoff = vsl_clamp((.475*e->sample_rate-f*e->combustion.stretch)/(.035*e->sample_rate),0,1);
        re *= cutoff; im *= cutoff;rr*=cutoff;ri*=cutoff;
        e->dna.target_real[k-1] = re;
        e->dna.target_imag[k-1] = im;
        e->dna.target_right_real[k-1]=rr;e->dna.target_right_imag[k-1]=ri;
        energy += .5*(re*re + im*im+rr*rr+ri*ri);
    }
    /* Stable loudness leaves load dynamics to the explicit envelope. */
    energy = .36 / sqrt(fmax(energy, .00001));
    e->dna.factory_scale=energy;
    for (k=0;k<VSL_PARTIALS;++k) {
        e->dna.target_real[k] *= energy;
        e->dna.target_imag[k] *= energy;
        e->dna.target_right_real[k]*=energy;e->dna.target_right_imag[k]*=energy;
    }
}
void vsl_dna_tick(VslEngine *e,double *left,double *right) {
    double phase = e->dna.custom_count?e->dna.pitch_phase:e->control.phase;
    int varied=e->combustion.mix>0&&!e->dna.custom_count&&e->smooth.profile==VSL_V10;
    double right_phase=phase+(varied?e->combustion.phase_delta[1]:0);
    double s,c,sk,ck,sr,cr,skr,ckr,output=0,r=0;
    double slew = 1-exp(-1/(.008*e->sample_rate));
    int k;
    if(varied)phase+=e->combustion.phase_delta[0];
    s=sin(phase);c=cos(phase);sk=s;ck=c;
    sr=sin(right_phase);cr=cos(right_phase);skr=sr;ckr=cr;
    for (k=0;k<VSL_PARTIALS;++k) {
        double next;
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
        double variation=e->dna.custom_count?1:1+e->smooth.irregularity*(.07*e->voice.idle*sin(e->detail.variation_phase)+.025*sin(phase*2.0));
        if(varied) {
            /* Replace the old forced opposite AM with independent bounded
               pressure-event variation. Mean crank phase is unchanged. */
            double mix=e->combustion.mix;
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
    char tag[24]; int version,n,i; double root,amp[VSL_PARTIALS],phase[VSL_PARTIALS];
    if (!f) return 0;
    if (fscanf(f,"%23s %d %lf %d",tag,&version,&root,&n)!=4 ||
        strcmp(tag,"VSL_DNA") || version!=1 || n<1 || n>VSL_PARTIALS ||
        !isfinite(root) || root<10 || root>4000) { fclose(f); return 0; }
    for(i=0;i<n;++i) {
        if(fscanf(f,"%lf %lf",&amp[i],&phase[i])!=2 || !isfinite(amp[i]) ||
           !isfinite(phase[i]) || amp[i]<0 || amp[i]>100) { fclose(f); return 0; }
    }
    fclose(f);
    memcpy(e->dna.custom_amp,amp,(size_t)n*sizeof(double));
    memcpy(e->dna.custom_phase,phase,(size_t)n*sizeof(double));
    e->dna.custom_count=n; e->dna.custom_root=root;e->dna.pitch_phase=0;
    return 1;
}
