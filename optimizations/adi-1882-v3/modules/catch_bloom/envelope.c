#include "envelope.h"
#include <math.h>
float cb_pulse(float u,float p,float q) {
    float at=p/(p+q);
    if(u<=0||u>=1)return 0;
    return expf(p*logf(u/at)+q*logf((1-u)/(1-at)));
}
float cb_follow(float current,float target,float coefficient) {
    return current+coefficient*(target-current);
}
