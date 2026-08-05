#define LOG(fmt,...) g(fmt, ##__VA_ARGS__)
LOG("m", 42, 3)
