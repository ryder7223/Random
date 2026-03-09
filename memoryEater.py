import subprocess
import sys
import threading

def runProcess():
    subprocess.check_call([sys.executable] + sys.argv)

thread1 = threading.Thread(target=runProcess)
thread2 = threading.Thread(target=runProcess)

thread1.start()
thread2.start()

thread1.join()
thread2.join()
