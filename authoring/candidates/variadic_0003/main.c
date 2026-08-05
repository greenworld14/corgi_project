#define COUNT(...) NARG(__VA_ARGS__, 3, 2, 1, 0)
#define NARG(a,b,c,d,n,...) n
COUNT(x, y)
