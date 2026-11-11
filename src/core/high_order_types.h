#ifndef VSL_HIGH_ORDER_TYPES_H
#define VSL_HIGH_ORDER_TYPES_H
#define VSL_HIGH_ORDERS 512
#define VSL_CONTINUATION_FIRST 26
#define VSL_CONTINUATION_LAST 48
#define VSL_CONTINUATION_COUNT (VSL_CONTINUATION_LAST-VSL_CONTINUATION_FIRST+1)
typedef struct {
    double amplitude[VSL_HIGH_ORDERS], target[VSL_HIGH_ORDERS];
    double continuation[2][VSL_CONTINUATION_COUNT], continuation_target[2][VSL_CONTINUATION_COUNT];
    int active;
} VslHighOrders;
#endif
