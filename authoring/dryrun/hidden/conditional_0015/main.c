#define V 0x1f
#if defined(V) && V > 1
big
#elif defined(V)
small
#else
none
#endif
