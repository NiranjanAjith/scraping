import os
import logging
from urllib.parse import urlparse
from datetime import datetime
from cryptography.fernet import Fernet

class Config:
    def __init__(self):
        self.encryption_key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.encryption_key)

        self.folders = {
            "pdfs": os.path.join("data", "pdfs"),
            "logs": os.path.join("data", "logs", datetime.now().strftime("%Y/%m")),
            "csv_files": os.path.join("data", "csv"),
        }

        self.files = {
            "captcha_image": "captcha.png",
            "all_urls_csv": "all_urls.csv",
            "good_urls_csv": "good_urls.csv",
            "bad_urls_csv": "bad_urls.csv",
            "resume_state": "resume_state.pkl",
            "log_file": f"crawler_log_{datetime.now().strftime('%Y%m%d')}.txt",
            "csv_error_log": f"csv_error_log_{datetime.now().strftime('%Y%m%d')}.csv",
        }

        self.directories = {
            "pdf_dir": self.get_full_path("pdfs"),
            "log_file": self.get_full_path("logs", "log_file"),
            "captcha_image_path": self.get_full_path("pdfs", "captcha_image"),
            "all_csv": self.get_full_path("csv_files", "all_urls_csv"),
            "good_csv": self.get_full_path("csv_files", "good_urls_csv"),
            "bad_csv": self.get_full_path("csv_files", "bad_urls_csv"),
            "resume_state_file": self.get_full_path("csv_files", "resume_state"),
            "csv_error_log": self.get_full_path("csv_files", "csv_error_log"),
        }

        self.links = {
            "search_url": "https://judgments.ecourts.gov.in/pdfsearch/",
            "captcha_image_element": "captcha_image",
            "pdf_url_pattern": "",
        }

        self.html_elements = {
            "captcha_id": ("id", 'captcha'),
            "captcha_input_id": ("id", 'captcha_input'),
            "submit_button_xpath": ("xpath", '//input[@type="submit"]'),
            "pdf_button_xpath": ("xpath", "//button[@role='link' and contains(@onclick, 'open_pdf')]"),
            "next_page_xpath": ("xpath", "//a[contains(@class, 'next-page')]"),
        }

        self.site_specific = {
            "click_pdf_button_js": "return {onclick_script}",
            "form_submit_js": "document.getElementById('captcha_form').submit();",
        }

        self.misc_settings = {
            "user_agents": [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
            ],
            "max_retries": 3,
            "retry_delay": 5,
            "max_workers": 5,
            "ai_captcha_service_url": self.encrypt("https://api.captchaservice.com/solve"),
            "ai_captcha_service_api_key": self.encrypt("your-api-key-here"),
            "element_timeout": 10,
            "page_load_timeout": 30,
            "headless": False,
            "proxy_list": [
                "http://proxy1.example.com:8080",
                "http://proxy2.example.com:8080"
            ],
            "rate_limit": 1  # requests per second
        }

    def encrypt(self, data: str) -> bytes:
        return self.cipher_suite.encrypt(data.encode())

    def decrypt(self, data: bytes) -> str:
        return self.cipher_suite.decrypt(data).decode()

    def get_full_path(self, folder_key, file_key=None):
        folder = self.folders.get(folder_key)
        if not folder:
            raise ValueError(f"Invalid folder key: {folder_key}")

        if not file_key:
            return folder

        file_name = self.files.get(file_key)
        if not file_name:
            raise ValueError(f"Invalid file key: {file_key}")

        return os.path.join(folder, file_name)

    def create_directories(self):
        for folder_path in self.folders.values():
            if folder_path and not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
                logging.info(f"Created directory: {folder_path}")
            else:
                logging.info(f"Directory already exists: {folder_path}")

    def validate_file_paths(self):
        for file_key, file_path in self.directories.items():
            if file_path:
                folder = os.path.dirname(file_path)
                if not os.path.exists(folder):
                    logging.warning(f"Directory for {file_key} does not exist. Creating it: {folder}")
                    os.makedirs(folder, exist_ok=True)
                else:
                    logging.info(f"Valid directory for {file_key}: {folder}")

    def validate_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception as e:
            logging.error(f"Invalid URL: {url} - {str(e)}")
            return False

    def validate_html_elements(self):
        required_elements = ['captcha_id', 'captcha_input_id', 'submit_button_xpath', 'pdf_button_xpath']
        for element in required_elements:
            if not self.html_elements.get(element):
                logging.error(f"HTML element {element} is missing in the configuration.")
            else:
                logging.info(f"HTML element validated: {element}")

    def validate_all_config(self):
        self.create_directories()
        self.validate_file_paths()
        self.validate_html_elements()
        
        if not self.validate_url(self.links['search_url']):
            logging.error("Invalid search URL in configuration")
            return False

        if not self.misc_settings.get('user_agents'):
            logging.error("No user agents specified in configuration")
            return False

        if not self.misc_settings.get('proxy_list'):
            logging.warning("No proxy list specified in configuration")

        return True

    def get_random_user_agent(self):
        import random
        return random.choice(self.misc_settings['user_agents'])

    def get_random_proxy(self):
        import random
        return random.choice(self.misc_settings['proxy_list'])

# Example Usage
if __name__ == "__main__":
    config = Config()
    if config.validate_all_config():
        print("Configuration is valid.")
        print(f"PDF Directory: {config.directories['pdf_dir']}")
        print(f"Search URL: {config.links['search_url']}")
        print(f"CAPTCHA Input ID: {config.html_elements['captcha_input_id']}")
        print(f"Random User Agent: {config.get_random_user_agent()}")
        print(f"Random Proxy: {config.get_random_proxy()}")
    else:
        print("Configuration is invalid. Please check the logs for details.")