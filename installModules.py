import subprocess
import importlib
import sys

requiredModules = {
    "requests": {
        "package": "requests"
    },
    "colorama": {
        "package": "colorama"
    },
    "GDReq": {
        "package": "GDReq",
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
