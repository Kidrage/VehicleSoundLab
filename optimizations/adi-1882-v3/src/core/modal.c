#include "modal.h"
#include <math.h>
#include <string.h>
#include "dsp/wave.h"
#define PI 3.14159265358979323846f
void vsl_mode_init(VslMode *m,float hz,float decay,float sr) {
    memset(m,0,sizeof *m);
    if(!isfinite(sr)||sr<1||!isfinite(hz)||hz<=0||hz>=sr*.40f||!isfinite(decay)||decay<=0)return;
    m->hz=hz;m->decay=decay;m->radius=expf(-1/(sr*decay));
    m->cosine=cosf(2*PI*hz/sr);m->sine=sinf(2*PI*hz/sr);
}
void vsl_mode_strike(VslMode *m,float amplitude,float elapsed) {
    float angle,gain,d;
    if(!m->hz||!isfinite(amplitude)||!isfinite(elapsed)||elapsed<0)return;
    angle=2*PI*m->hz*elapsed;d=elapsed/m->decay;
    /* Fractional sample strikes have tiny damping exponents. The cubic's
       relative error is below 7e-9 at d<=.02; long offsets use libm. */
    gain=amplitude*(d<=.02f?1-d+d*d*(.5f-d/6):expf(-d));
    if(fabsf(angle)<=10){m->real+=gain*vsl_sine(angle);m->imag+=gain*vsl_cosine(angle);}
    else {m->real+=gain*sinf(angle);m->imag+=gain*cosf(angle);}
}
float vsl_mode_tick(VslMode *m) {
    float real=m->radius*(m->cosine*m->real+m->sine*m->imag);
    m->imag=m->radius*(m->cosine*m->imag-m->sine*m->real);m->real=real;
    if(fabsf(m->real)+fabsf(m->imag)<1e-18f)m->real=m->imag=0;
    return m->real;
}
