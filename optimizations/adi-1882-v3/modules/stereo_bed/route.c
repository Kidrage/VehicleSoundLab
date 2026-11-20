#include "route.h"
int sb_layout_init(SbLayout *layout,unsigned channels) {
    if(!layout||(channels!=2&&channels!=12))return 0;
    layout->channels=channels;return 1;
}
void sb_route(const SbLayout *layout,const float stereo[2],float width,float *out) {
    float left=stereo[0],right=stereo[1];unsigned c;
    /* Exact identity at full width, including signed zero. */
    if(width!=1) {
        float mid=.5f*(left+right),side=.5f*(left-right)*width;
        left=mid+side;right=mid-side;
    }
    for(c=0;c<layout->channels;++c)out[c]=0;
    out[0]=left;out[1]=right;
}
