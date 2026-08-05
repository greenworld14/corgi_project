#define V 0
#if defined(V) && V > 1
big
#elif defined(V)
small
#else
none
#endif
