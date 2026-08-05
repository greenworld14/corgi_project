#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(foo/*c*/item   ==   "a\tb"   acc, 100  0x1f  100)
