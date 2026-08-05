#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(0   'x'   baz   42, val  buf  x)
