#ifndef VSL_EXCITATION_TYPES_H
#define VSL_EXCITATION_TYPES_H
typedef struct {
    double firing, pumping;
    double b0,a1,a2,x1[2],x2[2],y1[2],y2[2];
    int profile;
} VslExcitation;
#endif
