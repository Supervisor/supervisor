import time
import datetime

print("时间打印脚本已启动")

while True:
    now = datetime.datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(5) 