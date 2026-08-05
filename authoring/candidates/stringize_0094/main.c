#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR('x', bar/*c*/bar)
