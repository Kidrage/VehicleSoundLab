#include "test_models.h"
#include <math.h>
#include <string.h>
void bd_model(SdProfile *m,double root,unsigned harmonics,int texture) {
    unsigned h;
    memset(m,0,sizeof *m);m->rate=48000;m->window=1024;m->hop=256;
    m->base_hz=root;m->harmonics=harmonics;m->components=texture?2:0;
    if(texture){m->rho[0]=.6;m->rho[1]=-.2;}
    for(h=0;h<harmonics;++h) {
        SdHarmonic *z=m->harmonic+h;
        double p=.13*h,a=.08/(h+1);
        z->mean[0]=a*cos(p);z->mean[1]=a*sin(p);
        z->mean[2]=.7*a*cos(p+.4);z->mean[3]=.7*a*sin(p+.4);
        if(texture) {
            z->basis[0][0]=.0001;z->basis[1][3]=.00007;z->rho=.3;
            z->root[0][0]=.00003;z->root[2][2]=.00002;
        }
    }
}
