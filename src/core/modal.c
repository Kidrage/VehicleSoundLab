#include "modal.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
void vsl_mode_init(VslMode *m,double hz,double decay,double sr) {
    memset(m,0,sizeof *m);
    if(!isfinite(sr)||sr<1||!isfinite(hz)||hz<=0||hz>=sr*.40||!isfinite(decay)||decay<=0)return;
    m->hz=hz;m->decay=decay;m->radius=exp(-1/(sr*decay));
    m->cosine=cos(2*PI*hz/sr);m->sine=sin(2*PI*hz/sr);
}
void vsl_mode_strike(VslMode *m,double amplitude,double elapsed) {
    double angle,gain;
    if(!m->hz||!isfinite(amplitude)||!isfinite(elapsed)||elapsed<0)return;
    angle=2*PI*m->hz*elapsed;gain=amplitude*exp(-elapsed/m->decay);
    m->real+=gain*sin(angle);m->imag+=gain*cos(angle);
}
double vsl_mode_tick(VslMode *m) {
    double real=m->radius*(m->cosine*m->real+m->sine*m->imag);
    m->imag=m->radius*(m->cosine*m->imag-m->sine*m->real);m->real=real;
    if(fabs(m->real)+fabs(m->imag)<1e-18)m->real=m->imag=0;
    return m->real;
}
