from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from logging_manager import LoggingManager, ErrorType
from config import Config
import time
import functools

def retry(max_tries=3, delay=1, backoff=2, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tries = 0
            while tries < max_tries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    tries += 1
                    if tries == max_tries:
                        raise
                    time.sleep(delay * (backoff ** (tries - 1)))
        return wrapper
    return decorator

class SeleniumHandler:
    def __init__(self, config: Config, logging_manager: LoggingManager):
        self.config = config
        self.logging_manager = logging_manager
        self.driver = None
        self.wait = None

    def __enter__(self):
        self.setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_driver()

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument(f"user-agent={self.config.misc_settings['user_agent']}")
        if self.config.misc_settings.get('headless', False):
            chrome_options.add_argument("--headless")

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, self.config.misc_settings.get("element_timeout", 10))
        self.logging_manager.log_info("WebDriver setup complete.")

    def close_driver(self):
        if self.driver:
            self.driver.quit()
            self.logging_manager.log_info("WebDriver closed.")

    def wait_for_element(self, locator, timeout=None):
        timeout = timeout or self.config.misc_settings.get("element_timeout", 10)
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            self.logging_manager.log_info(f"Element located: {locator}")
            return element
        except TimeoutException as e:
            self.logging_manager.log_error(f"Element not found within {timeout} seconds: {locator}", ErrorType.PARSING)
            raise

    @retry(exceptions=(ElementClickInterceptedException,))
    def click_element(self, locator):
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            self.logging_manager.log_info(f"Clicked element: {locator}")
        except (TimeoutException, NoSuchElementException) as e:
            self.logging_manager.log_error(f"Element not clickable or not found: {locator}", ErrorType.PARSING)
            raise

    def fill_input_field(self, locator, value):
        try:
            input_field = self.wait.until(EC.visibility_of_element_located(locator))
            input_field.clear()
            input_field.send_keys(value)
            self.logging_manager.log_info(f"Filled input field {locator} with value: {value}")
        except (TimeoutException, NoSuchElementException) as e:
            self.logging_manager.log_error(f"Error filling input field {locator}", ErrorType.PARSING)
            raise

    def submit_form(self, submit_button_locator):
        try:
            self.click_element(submit_button_locator)
            self.wait_for_page_load()
            self.logging_manager.log_info(f"Form submitted by clicking: {submit_button_locator}")
        except Exception as e:
            self.logging_manager.log_error(f"Error submitting form", ErrorType.PARSING)
            raise

    def scroll_to_element(self, locator):
        try:
            element = self.wait_for_element(locator)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)  # Allow time for scroll to complete
            self.logging_manager.log_info(f"Scrolled to element: {locator}")
        except Exception as e:
            self.logging_manager.log_error(f"Error scrolling to element", ErrorType.PARSING)
            raise

    def trigger_js_function(self, js_code):
        try:
            result = self.driver.execute_async_script(f"""
                var callback = arguments[arguments.length - 1];
                {js_code}
                callback(result);
            """)
            self.logging_manager.log_info("JavaScript function triggered successfully.")
            return result
        except Exception as e:
            self.logging_manager.log_error(f"Error executing JavaScript", ErrorType.PARSING)
            raise

    def fetch_pdf_link(self):
        try:
            pdf_button_locator = (By.XPATH, self.config.get_html_element("pdf_button_xpath"))
            self.click_element(pdf_button_locator)
            self.logging_manager.log_info("PDF button clicked, triggering JavaScript.")

            js_function = self.config.get_site_specific("click_pdf_button_js")
            pdf_link = self.trigger_js_function(js_function)
            
            if pdf_link:
                self.logging_manager.log_info(f"PDF link generated: {pdf_link}")
                return pdf_link
            else:
                self.logging_manager.log_error("No PDF link found after JavaScript execution.", ErrorType.PARSING)
                return None
        except Exception as e:
            self.logging_manager.log_error(f"Error fetching PDF link", ErrorType.PARSING)
            raise

    def wait_for_page_load(self, timeout=None):
        timeout = timeout or self.config.misc_settings.get("page_load_timeout", 30)
        try:
            self.wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
            self.logging_manager.log_info("Page loaded successfully.")
        except TimeoutException:
            self.logging_manager.log_error(f"Page load timeout after {timeout} seconds", ErrorType.NETWORK)
            raise

    def get_element_attribute(self, locator, attribute):
        try:
            element = self.wait_for_element(locator)
            value = element.get_attribute(attribute)
            self.logging_manager.log_info(f"Retrieved attribute '{attribute}' from element {locator}")
            return value
        except Exception as e:
            self.logging_manager.log_error(f"Error getting element attribute", ErrorType.PARSING)
            raise

    def get_element_text(self, locator):
        try:
            element = self.wait_for_element(locator)
            text = element.text
            self.logging_manager.log_info(f"Retrieved text from element {locator}")
            return text
        except Exception as e:
            self.logging_manager.log_error(f"Error getting element text", ErrorType.PARSING)
            raise

    def take_screenshot(self, filename):
        try:
            self.driver.save_screenshot(filename)
            self.logging_manager.log_info(f"Screenshot saved as {filename}")
        except Exception as e:
            self.logging_manager.log_error(f"Error taking screenshot", ErrorType.FILE_IO)
            raise