import time

print("计数器脚本已启动")

count = 0
while True:
    count += 1
    print(f"当前计数: {count}")
    time.sleep(2) 