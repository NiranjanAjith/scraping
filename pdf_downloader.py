# pdf_downloader.py

import os
import requests
from selenium_handler import SeleniumHandler
from logging_manager import LoggingManager, ErrorType
from config import Config
import time

class PDFDownloader:
    def __init__(self, config: Config, selenium_handler: SeleniumHandler, logging_manager: LoggingManager):
        self.config = config
        self.selenium_handler = selenium_handler
        self.logging_manager = logging_manager
        self.download_dir = self.config.get_directory("pdf_dir")
        self.retry_delay = self.config.misc_settings.get("retry_delay", 5)
        self.max_retries = self.config.misc_settings.get("max_retries", 3)

    def _create_pdf_filename(self, download_url):
        """Generates the file name for the downloaded PDF based on its URL."""
        file_name = download_url.split("/")[-1]
        return os.path.join(self.download_dir, file_name)

    def _is_pdf_valid(self, file_path):
        """Verifies if the downloaded file is a valid PDF by checking its header."""
        try:
            with open(file_path, 'rb') as pdf_file:
                header = pdf_file.read(4)
                return header == b'%PDF'
        except Exception as e:
            self.logging_manager.log_error(f"Error validating PDF file: {str(e)}", ErrorType.FILE_IO)
            return False

    def download_pdf(self, pdf_link):
        """Downloads the PDF from the provided link, retries if necessary, and validates the download."""
        pdf_filename = self._create_pdf_filename(pdf_link)

        if os.path.exists(pdf_filename):
            self.logging_manager.log_info(f"PDF already exists at: {pdf_filename}. Skipping download.")
            self.logging_manager.log_to_csv(file_type="all", record=[pdf_link, "Skipped", "PDF already exists"])
            return pdf_filename

        self.logging_manager.log_info(f"Attempting to download PDF from: {pdf_link}")
        self.logging_manager.log_to_csv(file_type="all", record=[pdf_link, "Attempting", "Download started"])

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(pdf_link, stream=True, timeout=self.config.misc_settings.get("network_timeout", 10))
                
                if response.status_code == 200:
                    with open(pdf_filename, 'wb') as pdf_file:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                pdf_file.write(chunk)
                    self.logging_manager.log_info(f"PDF downloaded successfully: {pdf_filename}")

                    if self._is_pdf_valid(pdf_filename):
                        self.logging_manager.log_info(f"PDF validation successful: {pdf_filename}")
                        self.logging_manager.log_to_csv(file_type="all", record=[pdf_link, "Success", "PDF downloaded and valid"])
                        self.logging_manager.log_to_csv(file_type="good", record=[pdf_link, "Success", "PDF downloaded and valid"])
                        return pdf_filename
                    else:
                        self.logging_manager.log_error(f"Invalid PDF file format: {pdf_filename}", ErrorType.FILE_IO)
                        self.logging_manager.log_to_csv(file_type="all", record=[pdf_link, "Failed", "Invalid PDF format"])
                        self.logging_manager.log_to_csv(file_type="bad", record=[pdf_link, "Failed", "Invalid PDF format"])
                        raise Exception("Invalid PDF file format.")
                else:
                    raise Exception(f"Failed to download PDF. Status code: {response.status_code}")
            except Exception as e:
                self.logging_manager.log_error(f"Error downloading PDF (Attempt {attempt}/{self.max_retries}): {str(e)}", ErrorType.NETWORK)
                self.logging_manager.log_to_csv(file_type="all", record=[pdf_link, "Failed", str(e)])
                if attempt < self.max_retries:
                    self.logging_manager.log_info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)

        self.logging_manager.log_error("PDF download failed after maximum retries.", ErrorType.NETWORK)
        self.logging_manager.log_to_csv(file_type="bad", record=[pdf_link, "Failed", "Maximum retries exceeded"])
        return None

    def start_pdf_download_process(self):
        """Coordinates the PDF download process with Selenium to fetch the link."""
        try:
            self.logging_manager.log_info("Starting PDF download process...")
            pdf_link = self.selenium_handler.fetch_pdf_link()

            if pdf_link:
                return self.download_pdf(pdf_link)
            else:
                self.logging_manager.log_error("No valid PDF link found.", ErrorType.PARSING)
                self.logging_manager.log_to_csv(file_type="bad", record=[pdf_link, "Failed", "No valid PDF link found"])
                return None
        except Exception as e:
            self.logging_manager.log_error(f"Unexpected error during PDF download process: {str(e)}", ErrorType.UNKNOWN)
            return None

# Example usage
if __name__ == "__main__":
    config = Config()
    logging_manager = LoggingManager(config)

    if logging_manager.validate_config():
        with SeleniumHandler(config, logging_manager) as selenium_handler:
            selenium_handler.driver.get(config.get_link("pdf_page_url"))
            pdf_downloader = PDFDownloader(config, selenium_handler, logging_manager)
            
            try:
                pdf_file = pdf_downloader.start_pdf_download_process()
                if pdf_file:
                    logging_manager.log_step(["PDF", "Success"], is_successful=True)
                    print(f"PDF downloaded and saved at: {pdf_file}")
                else:
                    logging_manager.log_step(["PDF", "Failed"], is_successful=False)
                    print("Failed to download PDF. Aborting process.")
            except Exception as e:
                logging_manager.log_error(f"Unexpected error during PDF download: {str(e)}", ErrorType.UNKNOWN)
    else:
        print("Configuration validation failed. Please check your config file.")
