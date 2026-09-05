"""
Windowkill version 4.0.6b
"""

import subprocess
import importlib
import sys

requiredModules = {
    "processTool": {
        "package": "processTool",
        "args": ["-i", "https://test.pypi.org/simple/"]
    }
}

def installMissingModules(modules):
    installedSomething = False
    for importName, moduleInfo in modules.items():
        try:
            importlib.import_module(importName)
            
        except ImportError:
            packageName = moduleInfo["package"]
            extraArgs = moduleInfo.get("args", [])
            print(f"{packageName} is not installed. Installing...")
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                *extraArgs,
                packageName])
            installedSomething = True
    if installedSomething:
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()

installMissingModules(requiredModules)


from processTool import Process

wk = Process("windowkill-vulkan.exe")
wkBase = wk.moduleBase

currencyPaths = (
	[0x448, 0x238, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x348, 0x288, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x60, 0x238, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x448, 0x170, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x348, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x348, 0x188, 0x130, 0x18, 0x68, 0x28, 0x458],
	[0x448, 0x468, 0x1C0, 0x18, 0x68, 0x28, 0x458],
	[0x348, 0x238, 0x1C0, 0x18, 0x68, 0x28, 0x458]
)


currency = None
for item in currencyPaths:
	currency = wk.resolvePointer(wkBase+0x33EC840, item)
	if currency is not None:
		break


if currency is None:
	raise RuntimeError("Could not read currency")

currencyValue = wk.readUInt(currency)
print(f"Current currency value: {currencyValue}")
newCurrency = int(input("Enter new currency value: "))
wk.writeUInt(currency, newCurrency)
input("Updated currency!")