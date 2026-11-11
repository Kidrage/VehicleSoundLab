#include "propagation.h"
#include "profiles/propagation.h"
#include <math.h>
static double bound(double x,double low,double high) { return fmax(low,fmin(high,x)); }
void vsl_propagation_init(VslPropagation *s) {
    int phase,j;const double pi=3.14159265358979323846;
    for(phase=0;phase<=VSL_PATH_PHASES;++phase) {
        double u=phase/(double)VSL_PATH_PHASES,sum=0,moment=0;
        for(j=0;j<VSL_PATH_TAPS;++j) {
            double offset=j-VSL_PATH_TAPS/2,z=offset-u;
            double w=fabs(z)<VSL_PATH_TAPS/2?.42+.5*cos(pi*z/(VSL_PATH_TAPS/2))+.08*cos(2*pi*z/(VSL_PATH_TAPS/2)):0;
            double sinc=fabs(z)<1e-12?1:(fabs(z-round(z))<1e-12?0:sin(pi*z)/(pi*z));
            s->kernel[phase][j]=sinc*w;sum+=s->kernel[phase][j];
        }
        for(j=0;j<VSL_PATH_TAPS;++j) { s->kernel[phase][j]/=sum;moment+=(j-VSL_PATH_TAPS/2)*s->kernel[phase][j]; }
        /* Exact DC gain/first moment, including interpolated table phases. */
        s->kernel[phase][VSL_PATH_TAPS/2]-=u-moment;
        s->kernel[phase][VSL_PATH_TAPS/2+1]+=u-moment;
    }
    s->kernel_ready=1;
}
void vsl_propagation_target(VslPropagation *s,int object,const VslObjectInfo *o,
    double lx,double ly,double lz,double sr) {
    const VslPropagationProfile *p=vsl_propagation_profile();int path;
    double x=o->x-lx,y=o->y-ly,z=o->z-lz;
    double centre=sqrt(x*x+y*y+z*z),lateral=y/fmax(centre,p->minimum_distance_m);
    if(object==0)s->clamped_paths=0;
    if(!s->kernel_ready)vsl_propagation_init(s);
    s->follow=1-exp(-1/(p->follow_seconds*sr));
    s->shadow_coefficient=1-exp(-2*3.14159265358979323846*p->shadow_hz/sr);
    for(path=0;path<VSL_PATH_COUNT;++path) {
        double ear=path==VSL_PATH_LEFT?p->ear_spacing_m*.5:path==VSL_PATH_RIGHT?-p->ear_spacing_m*.5:0;
        double distance=sqrt(x*x+(y-ear)*(y-ear)+z*z);
        /* Common FIR latency is explicit; never clamp a short physical path
           into a different acoustic distance or interaural time difference. */
        double delay=distance/p->speed_mps*sr+VSL_PATH_LATENCY;
        if(delay<VSL_PATH_TAPS/2+1||delay>VSL_PATH_BUFFER-VSL_PATH_TAPS/2-1)++s->clamped_paths;
        s->target_delay[object][path]=bound(delay,VSL_PATH_TAPS/2+1,VSL_PATH_BUFFER-VSL_PATH_TAPS/2-1);
        s->target_gain[object][path]=(path==VSL_PATH_CENTRE?1:.7071067811865475)*
            p->reference_distance_m/fmax(distance,p->minimum_distance_m);
        if(!s->ready) {
            s->delay[object][path]=s->target_delay[object][path];
            s->gain[object][path]=s->target_gain[object][path];
        }
        if(path<2) {
            s->target_shadow[object][path]=p->shadow_fraction*fmax(0,(path==VSL_PATH_LEFT?-1:1)*lateral);
            if(!s->ready)s->shadow[object][path]=s->target_shadow[object][path];
        }
    }
    if(object==VSL_OBJECTS-1)s->ready=1;
}
void vsl_propagation_begin(VslPropagation *s,int enabled) {
    double target=enabled?1:0;
    s->mix+=s->follow*(target-s->mix);
    if(fabs(target-s->mix)<1e-9)s->mix=target;
}
static double delayed(const VslPropagation *s,int object,double delay) {
    unsigned whole=(unsigned)delay;
    double scaled=(delay-whole)*VSL_PATH_PHASES,result=0;
    unsigned phase=(unsigned)scaled;double u=scaled-phase;int j;
    unsigned at=(s->cursor+VSL_PATH_BUFFER-whole+VSL_PATH_TAPS/2)%VSL_PATH_BUFFER;
    /* Table-interpolated 25-tap Blackman sinc. Full delay keeps every tap
       causal. Finite-window HF error is measured by the exported C probe. */
    for(j=0;j<VSL_PATH_TAPS;++j) {
        double coefficient=s->kernel[phase][j]+u*(s->kernel[phase+1][j]-s->kernel[phase][j]);
        result+=coefficient*s->history[object][(at+VSL_PATH_BUFFER-j)%VSL_PATH_BUFFER];
    }
    return result;
}
void vsl_propagation_tick(VslPropagation *s,int object,double input,double paths[VSL_PATH_COUNT]) {
    int path;s->history[object][s->cursor]=(float)input;
    for(path=0;path<VSL_PATH_COUNT;++path) {
        double x;
        s->delay[object][path]+=s->follow*(s->target_delay[object][path]-s->delay[object][path]);
        s->gain[object][path]+=s->follow*(s->target_gain[object][path]-s->gain[object][path]);
        x=delayed(s,object,s->delay[object][path]);
        if(path<2) {
            s->shadow[object][path]+=s->follow*(s->target_shadow[object][path]-s->shadow[object][path]);
            s->shadow_low[object][path]+=s->shadow_coefficient*(x-s->shadow_low[object][path]);
            x+=(s->shadow_low[object][path]-x)*s->shadow[object][path];
        }
        paths[path]=x*s->gain[object][path];
    }
}
void vsl_propagation_advance(VslPropagation *s) { s->cursor=(s->cursor+1)%VSL_PATH_BUFFER; }
