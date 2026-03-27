import subprocess
import importlib
import sys

requiredModules = {
    "requests": "requests"
}

def installMissingModules(modules):
    installedSomething = False

    for importName, pipName in modules.items():
        try:
            importlib.import_module(importName)
        except ImportError:
            print(f"{pipName} is not installed. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pipName])
            installedSomething = True

    if installedSomething:
        subprocess.check_call([sys.executable] + sys.argv)
        sys.exit()

installMissingModules(requiredModules)
