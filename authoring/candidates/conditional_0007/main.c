#define V 42
#if defined(V) && V > 1
big
#elif defined(V)
small
#else
none
#endif
