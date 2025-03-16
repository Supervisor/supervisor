import time
import psutil

print("CPU监控脚本已启动")

while True:
    print(f"CPU使用率: {psutil.cpu_percent(interval=1)}%")
    for i, percentage in enumerate(psutil.cpu_percent(interval=1, percpu=True)):
        print(f"CPU {i}: {percentage}%")
    time.sleep(8) 