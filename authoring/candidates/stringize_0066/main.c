#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(foo  +  buf  2, a   '\n')
