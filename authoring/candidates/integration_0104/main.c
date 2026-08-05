#define STR(x) #x
#define XSTR(x) STR(x)
#define CAT(a,b) a##b
#define MAX(a,b) ((a)>(b)?(a):(b))
#define VERSION 1
#define NAME(n) CAT(sym_, n)
#if VERSION >= 1
int NAME(item) = MAX(0x1f, 3);
const char* v = XSTR(VERSION);
#else
int NAME(fallback);
#endif
#define APPLY(f, ...) f(__VA_ARGS__)
APPLY(callback, 0x1f, node)
