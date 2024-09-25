# crawler.py

from config import Config
from logging_manager import LoggingManager
from selenium_handler import SeleniumHandler
from captcha_handler import CaptchaHandler
from pdf_downloader import PdfDownloader
from bs4 import BeautifulSoup
import time

class Crawler:
    def __init__(self, config: Config, logging_manager: LoggingManager):
        self.config = config
        self.logging_manager = logging_manager
        self.selenium_handler = SeleniumHandler(config, logging_manager)
        self.captcha_handler = CaptchaHandler(config, self.selenium_handler, logging_manager)
        self.pdf_downloader = PdfDownloader(config, logging_manager)

    def fetch_content(self):
        # Use BeautifulSoup to parse and get content from the page
        soup = BeautifulSoup(self.selenium_handler.driver.page_source, 'html.parser')
        content_element = soup.select_one(self.config.get_html_element("content_selector"))
        return content_element.get_text(strip=True) if content_element else None

    def run(self):
        try:
            with self.selenium_handler:
                self.selenium_handler.driver.get(self.config.get_link("domain_url"))

                # Wait for a while for the page to load
                time.sleep(self.config.misc_settings.get("page_load_delay", 5))

                # Check if CAPTCHA is present
                if self.selenium_handler.driver.page_source.lower().find("captcha") != -1:
                    self.logging_manager.log_warning("CAPTCHA detected. Initiating CAPTCHA handling...")
                    if not self.captcha_handler.start_captcha_process():
                        self.logging_manager.log_error("CAPTCHA handling failed. Exiting.")
                        return

                # Fetch the element based on provided configuration
                element_locator = self.config.get_html_element("element_id")
                element_text = self.selenium_handler.get_element_text(element_locator)

                # Determine the tag type of the fetched element
                element_tag = self.selenium_handler.get_element_attribute(element_locator, 'tagName').lower()

                # Use PDF downloader for links/buttons, and BeautifulSoup for content elements
                if element_tag in ['a', 'button', 'link']:
                    self.logging_manager.log_info("Triggering PDF download...")
                    pdf_link = self.pdf_downloader.fetch_pdf_link()
                    if pdf_link:
                        self.pdf_downloader.download_pdf(pdf_link)
                elif element_tag in ['p', 'span', 'div']:
                    content = self.fetch_content()
                    if content:
                        self.logging_manager.log_step([self.config.get_link("domain_url"), content], is_successful=True)
                        print(f"Fetched content: {content}")
                    else:
                        self.logging_manager.log_warning("No content found.")
                else:
                    self.logging_manager.log_warning(f"Unhandled element type: {element_tag}")

        except Exception as e:
            self.logging_manager.log_error(f"Unexpected error during crawling: {str(e)}")

# Example usage
if __name__ == "__main__":
    config = Config()
    logging_manager = LoggingManager(config)

    if logging_manager.validate_config():
        crawler = Crawler(config, logging_manager)
        crawler.run()
    else:
        print("Configuration validation failed. Please check your config file.")
