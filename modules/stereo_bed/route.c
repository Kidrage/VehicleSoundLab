#include "route.h"
int sb_layout_init(SbLayout *layout,unsigned channels) {
    if(!layout||(channels!=2&&channels!=12))return 0;
    layout->channels=channels;return 1;
}
void sb_route(const SbLayout *layout,const double stereo[2],double width,double *out) {
    double left=stereo[0],right=stereo[1];unsigned c;
    /* Exact identity at full width, including signed zero. */
    if(width!=1) {
        double mid=.5*(left+right),side=.5*(left-right)*width;
        left=mid+side;right=mid-side;
    }
    for(c=0;c<layout->channels;++c)out[c]=0;
    out[0]=left;out[1]=right;
}
