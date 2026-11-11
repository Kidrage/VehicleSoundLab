#include "scope.h"
#if defined(_M_X64) || defined(__x86_64__)
#include <xmmintrin.h>
#define RN_MXCSR 1
#else
#define RN_MXCSR 0
#endif

int rn_scope_available(void) { return RN_MXCSR; }
RnScope rn_scope_enter(void) {
    RnScope scope={0,0};
#if RN_MXCSR
    scope.saved=_mm_getcsr();scope.active=1;
    _mm_setcsr(scope.saved|0x8040u);
#endif
    return scope;
}
void rn_scope_leave(RnScope scope) {
#if RN_MXCSR
    if(scope.active)_mm_setcsr(scope.saved);
#else
    (void)scope;
#endif
}
