#define V 1
#if defined(V) && V > 1
big
#elif defined(V)
small
#else
none
#endif
