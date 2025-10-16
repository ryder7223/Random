from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def open_chrome():
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)  # Keep window open

    # This will let Selenium find ChromeDriver automatically
    driver = webdriver.Chrome(options=chrome_options)
    
    driver.get("about:blank")

    # Keep script running until browser is closed
    driver.wait = True
    input("Press Enter to quit the script (browser will stay open due to detach=True)...")

if __name__ == "__main__":
    open_chrome()