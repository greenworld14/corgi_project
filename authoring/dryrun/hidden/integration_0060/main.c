#define STR(x) #x
#define XSTR(x) STR(x)
#define CAT(a,b) a##b
#define MAX(a,b) ((a)>(b)?(a):(b))
#define VERSION 0x1f
#define NAME(n) CAT(sym_, n)
#if VERSION >= 1
int NAME(acc) = MAX(7, 42);
const char* v = XSTR(VERSION);
#else
int NAME(fallback);
#endif
#define APPLY(f, ...) f(__VA_ARGS__)
APPLY(callback, 2, b)
