#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(c   1000000   foo/*c*/bar   010, ~   a)
