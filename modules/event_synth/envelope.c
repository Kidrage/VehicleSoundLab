#include "internal.h"
double es_attack(uint64_t age,double seconds) {
    double t=seconds>0?(double)age/(ES_RATE*seconds):1;
    if(t>=1)return 1;
    return t*t*(3-2*t);
}
