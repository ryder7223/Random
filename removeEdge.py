import subprocess
import requests
import tempfile
import os
import logging

def log(message):
    logging.info(message)
    print(message)

def run_edge_vanisher():
    log("Starting Edge Vanisher script execution...")
    try:
        script_url = "https://raw.githubusercontent.com/ryder7223/Random/refs/heads/main/edge_vanisher.ps1"
        temp_dir = tempfile.gettempdir()
        script_path = os.path.join(temp_dir, "edge_vanisher.ps1")
        log(f"Attempting to download Edge Vanisher script from: {script_url}")
        log(f"Target script path: {script_path}")
        
        response = requests.get(script_url)
        log(f"Download response status code: {response.status_code}")
        
        with open(script_path, "wb") as file:
            file.write(response.content)
        log("Edge Vanisher script successfully saved to disk")
        
        powershell_command = (
            f"Set-ExecutionPolicy Bypass -Scope Process -Force; "
            f"& '{script_path}'; exit" 
        )
        log(f"Executing PowerShell command: {powershell_command}")
        
        process = subprocess.run(
            ["powershell", "-Command", powershell_command],
            capture_output=True,
            text=True
        )
        
        if process.returncode == 0:
            log("Edge Vanisher execution completed successfully")
            log(f"Process output: {process.stdout}")

        else:
            log(f"Edge Vanisher execution failed with return code: {process.returncode}")
            log(f"Process error: {process.stderr}")

    except requests.exceptions.RequestException as e:
        log(f"Network error during Edge Vanisher script download: {str(e)}")
    except IOError as e:
        log(f"File I/O error while saving Edge Vanisher script: {str(e)}")
    except Exception as e:
        log(f"Unexpected error during Edge Vanisher execution: {str(e)}")

run_edge_vanisher()