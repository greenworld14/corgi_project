#define LOG(fmt,...) g(fmt, ##__VA_ARGS__)
LOG("m", 0x1f, 42)
