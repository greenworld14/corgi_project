#define V 2
#if defined(V) && V > 1
big
#elif defined(V)
small
#else
none
#endif
