#include "scene.h"
#include "propagation.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
/* Vehicle coordinates, metres: +x front, +y left, +z up. Stereo is a monitor
   of these objects. Original objects remain available to a later spatial host. */
static const VslObjectInfo objects[VSL_OBJECTS]={
    {"exhaust_left",-1.8,.55,.4},{"exhaust_right",-1.8,-.55,.4},
    {"intake",-.6,0,.8},{"body",0,0,.45},{"mechanical",-.7,0,.65},
    {"air_left",-1.75,.6,.5},{"air_right",-1.75,-.6,.5},
    {"events",-1.8,0,.4},{"road",0,0,0},{"wind",1,0,1.2}
};
const VslObjectInfo *vsl_object_info(int i) { return &objects[i>=0&&i<VSL_OBJECTS?i:0]; }
const char *vsl_channel_name(int n,int i) {
    static const char *names[]={"FL","FR","FC","LFE","BL","BR","SL","SR","TFL","TFR","TBL","TBR"};
    return i>=0&&i<n&&i<12?names[i]:"invalid";
}
void vsl_listener_position(double perspective,double *x,double *y,double *z) {
    double cabin=vsl_clamp(perspective,0,1);*x=-3*(1-cabin)+.35*cabin;*y=.30*cabin;*z=.9;
}
void vsl_scene_update(VslEngine *e,int channels) {
    VslSpatial *s=&e->spatial; int i,c;
    const double az[12]={-30,30,0,0,-150,150,-90,90,-45,45,-135,135};
    /* Pan sign is display convention here: negative is left. */
    if(channels!=2&&channels!=12)return;
    s->channels=channels;s->ready=1;
    for(i=0;i<VSL_OBJECTS;++i) {
        double lx,ly,lz,x,y,z;
        vsl_listener_position(e->smooth.perspective,&lx,&ly,&lz);
        vsl_propagation_target(&s->propagation,i,&objects[i],lx,ly,lz,e->sample_rate);
        x=objects[i].x-lx;y=objects[i].y-ly;z=objects[i].z-lz;
        double angle=-atan2(y,x),pan=vsl_clamp(sin(angle)*e->smooth.width,-1,1),norm=0;
        memset(s->gain[i],0,sizeof s->gain[i]);
        s->elevation[i]=atan2(z,sqrt(x*x+y*y));
        if(channels==2) {
            s->gain[i][0]=cos((pan+1)*VSL_PI/4);
            s->gain[i][1]=sin((pan+1)*VSL_PI/4);
        } else {
            /* Normalised angular panning of direct vehicle objects to the bed.
               Height receives room reflections, never duplicated dry engine. */
            for(c=0;c<8;++c)if(c!=3) {
                double distance=cos(angle-az[c]*VSL_PI/180);
                double w=pow(fmax(0,distance),8);
                s->gain[i][c]=w;norm+=w*w;
            }
            norm=sqrt(fmax(norm,1e-20));
            for(c=0;c<8;++c)s->gain[i][c]/=norm;
        }
    }
}
void vsl_scene_tick(VslEngine *e,const VslObjectFrame *o,double *output,int channels) {
    VslSpatial *s=&e->spatial;int i,c;
    double a=1-exp(-2*VSL_PI*120/e->sample_rate),send=0,low=0;
    unsigned delay[2]={(unsigned)(.019*e->sample_rate),(unsigned)(.031*e->sample_rate)};
    if(!s->ready || s->channels!=channels)vsl_scene_update(e,channels);
    vsl_propagation_begin(&s->propagation,e->target.propagation);
    for(c=0;c<channels;++c)output[c]=0;
    for(i=0;i<VSL_OBJECTS;++i) {
        double x=o->sample[i],hi,paths[VSL_PATH_COUNT],blend=s->propagation.mix;
        double cabin=e->smooth.perspective,cutoff=i==VSL_BODY?800:2400;
        s->cabin_low[i]+=(1-exp(-2*VSL_PI*cutoff/e->sample_rate))*(x-s->cabin_low[i]);
        x=x*(1-.75*cabin)+s->cabin_low[i]*(.75*cabin);
        vsl_propagation_tick(&s->propagation,i,x,paths);
        s->propagation.centre_low[i]+=a*(paths[VSL_PATH_CENTRE]-s->propagation.centre_low[i]);
        s->low[i]+=a*(x-s->low[i]);hi=x-s->low[i];
        low+=s->low[i]*(1-blend)+s->propagation.centre_low[i]*blend;
        send+=x*.20;
        for(c=0;c<channels;++c) {
            double direct=channels==2?.70710678118*s->low[i]+hi*s->gain[i][c]:x*s->gain[i][c];
            if(channels==2)output[c]+=direct*(1-blend)+paths[c]*blend;
            else if(c!=3)output[c]+=direct*(1-blend)+paths[VSL_PATH_CENTRE]*s->gain[i][c]*blend;
        }
    }
    vsl_propagation_advance(&s->propagation);
    s->reflection[0][s->cursor]=send;
    s->reflection[1][s->cursor]=send*.87;
    for(c=0;c<channels;++c) {
        unsigned d=delay[c%2]+(unsigned)(c/2*71);
        double wet=s->reflection[c%2][(s->cursor+VSL_SPACE_DELAY-d%VSL_SPACE_DELAY)%VSL_SPACE_DELAY];
        if(channels==12 && c==3)output[c]=.22*low; /* separate low-pass feed, no boost */
        else output[c]+=e->smooth.space*wet*(channels==12&&c>=8?.35:.25);
    }
    s->cursor=(s->cursor+1)%VSL_SPACE_DELAY;
    for(c=0;c<channels;++c) {
        double x=output[c],hp=exp(-2*VSL_PI*28/e->sample_rate);
        output[c]=x-s->previous_input[c]+hp*s->previous_output[c];
        s->previous_input[c]=x;s->previous_output[c]=output[c];
    }
    /* Fold after the filters as well, including any old stereo filter tails. */
    if(channels==2) {
        double mid=.5*(output[0]+output[1]),side=.5*(output[0]-output[1])*e->smooth.width;
        output[0]=mid+side;output[1]=mid-side;
    }
}
