#include "envelope.h"
#include <math.h>
double cb_pulse(double u,double p,double q) {
    double at=p/(p+q);
    if(u<=0||u>=1)return 0;
    return exp(p*log(u/at)+q*log((1-u)/(1-at)));
}
double cb_follow(double current,double target,double coefficient) {
    return current+coefficient*(target-current);
}
