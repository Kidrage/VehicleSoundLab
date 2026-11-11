#ifndef VSL_RT_NUMERIC_SCOPE_H
#define VSL_RT_NUMERIC_SCOPE_H

/* A calling-thread scope, not voice state. On x64, only FTZ/DAZ are enabled;
   leave restores the complete incoming MXCSR, including status and rounding.
   Nesting is supported in LIFO order. Other architectures use a no-op scope. */
typedef struct { unsigned saved; int active; } RnScope;
int rn_scope_available(void);
RnScope rn_scope_enter(void);
void rn_scope_leave(RnScope scope);

#endif
