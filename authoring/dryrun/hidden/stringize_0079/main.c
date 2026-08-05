#define STR(x) #x
#define XSTR(x) STR(x)
#define PAIR(a,b) #a #b
PAIR(<<  3  0  a  bar/*c*/baz, val 2 010 '\n' val)
