from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
import time
import sys
import signal
import atexit
import os

# Captive portal details
website_link = "http://10.24.1.2:2280/cportal/ip/user_login.php?url=http://10.24.1.2:2280/"
username = "jssbh23"
password = "jssbh23"

# Initialize the browser (use Firefox)
geckodriver_path = "/usr/local/bin/geckodriver"  # Common location
if not os.path.exists(geckodriver_path):
    geckodriver_path = "./geckodriver"  # Fallback to current directory
    if not os.path.exists(geckodriver_path):
        print("Error: geckodriver not found. Please install it first:")
        print("1. Download from: https://github.com/mozilla/geckodriver/releases")
        print("2. Extract and place in /usr/local/bin/ or current directory")
        sys.exit(1)

service = Service(geckodriver_path)
options = Options()
options.headless = False
browser = None

def cleanup():
    """Cleanup function to ensure browser is closed."""
    global browser
    if browser:
        try:
            print("\nCleaning up - closing browser...")
            browser.quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")

# Register cleanup function to run at exit
atexit.register(cleanup)

# Register signal handlers
def signal_handler(signum, frame):
    """Handle termination signals."""
    print(f"\nReceived signal {signum}")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def initialize_browser():
    """Initialize the browser instance."""
    global browser
    if not browser:
        browser = webdriver.Firefox(service=service, options=options)
    return browser

def login():
    """Automates the login process."""
    print("Logging in...")
    try:
        browser.get(website_link)
        
        # Wait for the frameset to load
        print("Waiting for the page to load...")
        WebDriverWait(browser, 30).until(EC.presence_of_element_located((By.TAG_NAME, "frameset")))
        print("Frameset loaded.")

        # Switch to the login frame
        print("Switching to login frame...")
        WebDriverWait(browser, 10).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "login_win")))
        print("Switched to login frame.")

        # Now wait for the actual login form elements
        print("Waiting for login form...")
        WebDriverWait(browser, 15).until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
        print("Login form loaded.")

        # Find and fill username field
        username_element = browser.find_element(By.XPATH, "//input[@type='text']")
        username_element.clear()
        username_element.send_keys(username)
        print("Entered username.")

        # Find and fill password field
        password_element = browser.find_element(By.XPATH, "//input[@type='password']")
        password_element.clear()
        password_element.send_keys(password)
        print("Entered password.")

        # Check the Terms and Conditions checkbox if it exists
        try:
            checkbox = browser.find_element(By.XPATH, "//input[@type='checkbox']")
            if not checkbox.is_selected():
                checkbox.click()
                print("Checked Terms and Conditions.")
        except Exception as e:
            print(f"Note: No Terms and Conditions checkbox found: {e}")

        # Find and click the login button
        try:
            # Try multiple button selectors
            button_selectors = [
                "//button[contains(text(), 'LOGIN')]",
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//button[contains(@class, 'login')]",
                "//input[@value='Login']",
                "//button"
            ]
            
            login_button = None
            for selector in button_selectors:
                try:
                    login_button = browser.find_element(By.XPATH, selector)
                    if login_button and login_button.is_displayed():
                        break
                except:
                    continue

            if login_button and login_button.is_displayed():
                login_button.click()
                print("Clicked login button.")
            else:
                raise Exception("Could not find visible login button")

        except Exception as e:
            print(f"Error finding login button: {e}")
            # Try JavaScript click as fallback
            try:
                browser.execute_script("document.querySelector('input[type=\"submit\"], button[type=\"submit\"], button').click();")
                print("Clicked login button using JavaScript.")
            except Exception as js_e:
                print(f"JavaScript click also failed: {js_e}")
                raise

        # Switch back to default content
        browser.switch_to.default_content()
        print("Switched back to default content.")

        # Wait a moment to let the login process complete
        time.sleep(2)
        
        return True

    except Exception as e:
        print(f"Error during login: {str(e)}")
        print("Current page source:")
        print(browser.page_source[:2000])  # Print first 2000 chars for debugging
        return False

def check_login():
    """Checks if the login page is loaded (session expired), and re-login if needed."""
    try:
        # First check if we're on the login page
        current_url = browser.current_url
        if "login" in current_url.lower():
            # Check for "Already logged in" message
            try:
                already_logged_in = browser.find_element(By.XPATH, "//*[contains(text(), 'Already logged in')]")
                if already_logged_in:
                    print("Already logged in detected - session is active")
                    return True
            except:
                print("Detected login page. Attempting to login...")
                return login()
            
        # Try to find elements that indicate we're logged in
        try:
            # Look for elements that should be present when logged in
            WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Welcome') or contains(text(), 'Already logged in')]")))
            print("Session is still active")
            return True
        except:
            # If we can't find logged-in elements, try to find login form
            try:
                WebDriverWait(browser, 5).until(EC.presence_of_element_located((By.NAME, "usrname")))
                print("Session expired. Re-logging in...")
                return login()
            except:
                print("Could not determine session status. Refreshing page...")
                browser.refresh()
                return check_login()

    except Exception as e:
        print(f"Error checking login status: {e}")
        return False

def main():
    """Main loop that keeps running in the background to maintain the session."""
    try:
        # Initialize browser
        initialize_browser()
        
        # Initial login
        if not login():
            print("Initial login failed. Exiting...")
            cleanup()
            sys.exit(1)
            
        while True:
            # Check if the session is still active or if login is needed
            if not check_login():
                print("Login check failed. Attempting to recover...")
                browser.refresh()
                time.sleep(5)  # Wait before retrying
                continue

            # Wait for 30 minutes before checking again
            print(f"Waiting 30 minutes before next check... (Current time: {time.strftime('%H:%M:%S')})")
            time.sleep(1800)  # 30 minutes = 1800 seconds

    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        cleanup()
        sys.exit(0)

if __name__ == "__main__":
    main()

