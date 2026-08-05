#define STR(x) #x
#define XSTR(x) STR(x)
#define CAT(a,b) a##b
#define MAX(a,b) ((a)>(b)?(a):(b))
#define VERSION 010
#define NAME(n) CAT(sym_, n)
#if VERSION >= 1
int NAME(m) = MAX(0, 42);
const char* v = XSTR(VERSION);
#else
int NAME(fallback);
#endif
#define APPLY(f, ...) f(__VA_ARGS__)
APPLY(callback, 42, idx)
