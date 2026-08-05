#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(100  foo  buf  k, 010 b/*c*/x 0x1f)
