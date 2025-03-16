import time
import psutil

print("内存监控脚本已启动")

while True:
    memory = psutil.virtual_memory()
    print(f"内存使用率: {memory.percent}%")
    print(f"可用内存: {memory.available / (1024 * 1024):.2f} MB")
    time.sleep(10) 