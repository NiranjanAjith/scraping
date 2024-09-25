import os
import csv
import json
import logging
import time
import pickle
import tkinter as tk
import requests
from PIL import Image, ImageTk
from io import BytesIO
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from scrapy.crawler import CrawlerProcess
import scrapy

class Config:
    SEARCH_URL = "https://judgments.ecourts.gov.in/pdfsearch/"
    PDF_DIR = "pdfs"
    CAPTCHA_IMAGE_PATH = "captcha.png"
    ALL_CSV = "all_urls.csv"
    GOOD_CSV = "good_urls.csv"
    BAD_CSV = "bad_urls.csv"
    CRAWLER_LOG = "crawler_log.txt"
    RESUME_STATE_FILE = "resume_state.pkl"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36"
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    MAX_WORKERS = 5

class LoggingManager:
    def __init__(self, log_file="crawler_log.txt"):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def log(self, message, level=logging.INFO):
        logging.log(level, message)

class CaptchaHandler:
    def __init__(self, selenium_handler):
        self.selenium_handler = selenium_handler

    def handle_captcha(self):
        captcha_image_element = self.selenium_handler.wait_for_element(By.ID, 'captcha_image')
        captcha_image_url = captcha_image_element.get_attribute('src')
        captcha_image_url = self.selenium_handler.driver.current_url.split('?')[0] + captcha_image_url

        captcha_response = requests.get(captcha_image_url)
        captcha_image = Image.open(BytesIO(captcha_response.content))
        
        captcha_text = self.display_captcha_and_get_input(captcha_image)
        
        captcha_input = self.selenium_handler.driver.find_element(By.ID, 'captcha')
        captcha_input.send_keys(captcha_text)
        submit_button = self.selenium_handler.driver.find_element(By.XPATH, '//input[@type="submit"]')
        submit_button.click()

    def display_captcha_and_get_input(self, captcha_image):
        root = tk.Tk()
        root.title("CAPTCHA")
        
        captcha_photo = ImageTk.PhotoImage(captcha_image)
        label = tk.Label(root, image=captcha_photo)
        label.pack()
        
        entry = tk.Entry(root)
        entry.pack()
        
        captcha_text = []
        
        def submit():
            captcha_text.append(entry.get())
            root.quit()
        
        button = tk.Button(root, text="Submit", command=submit)
        button.pack()
        
        root.mainloop()
        root.destroy()
        
        return captcha_text[0]

class SeleniumHandler:
    def __init__(self, config):
        self.config = config
        self.setup_selenium()

    def setup_selenium(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"user-agent={self.config.USER_AGENT}")

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def wait_for_element(self, by, value):
        return self.wait.until(EC.presence_of_element_located((by, value)))

    def get_page(self, url):
        self.driver.get(url)

    def quit(self):
        self.driver.quit()

class PDFDownloader:
    def __init__(self, config, logging_manager):
        self.config = config
        self.logging_manager = logging_manager
        self.executor = ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS)

    def download_pdf(self, pdf_url):
        for attempt in range(self.config.MAX_RETRIES):
            try:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()
                pdf_name = self.get_unique_filename(pdf_url)

                with open(pdf_name, 'wb') as f:
                    f.write(response.content)

                if self.validate_pdf(pdf_name):
                    self.logging_manager.log(f"Downloaded and validated PDF: {pdf_name}")
                    self.log_pdf_details(pdf_url, "Success")
                    return True
                else:
                    self.logging_manager.log(f"Invalid PDF: {pdf_name}", logging.WARNING)
                    os.remove(pdf_name)
                    return False

            except requests.RequestException as e:
                self.logging_manager.log(f"Attempt {attempt + 1} failed for {pdf_url}: {e}", logging.ERROR)
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(self.config.RETRY_DELAY)

        self.log_pdf_details(pdf_url, "Failed")
        return False

    def download_pdfs(self, pdf_urls):
        future_to_url = {self.executor.submit(self.download_pdf, url): url for url in pdf_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()
            except Exception as e:
                self.logging_manager.log(f"Error downloading PDF {url}: {e}", logging.ERROR)

    def get_unique_filename(self, url):
        base_name = os.path.basename(urlparse(url).path)
        name, ext = os.path.splitext(base_name)
        counter = 1
        while os.path.exists(os.path.join(self.config.PDF_DIR, f"{name}_{counter}{ext}")):
            counter += 1
        return os.path.join(self.config.PDF_DIR, f"{name}_{counter}{ext}")

    def validate_pdf(self, pdf_path):
        try:
            with open(pdf_path, 'rb') as f:
                PdfReader(f)
            return True
        except:
            return False

    def log_pdf_details(self, pdf_url, status):
        self.log_to_csv(self.config.ALL_CSV, pdf_url, status)
        csv_file = self.config.GOOD_CSV if status == "Success" else self.config.BAD_CSV
        self.log_to_csv(csv_file, pdf_url, status)

    def log_to_csv(self, csv_file, pdf_url, status):
        with open(csv_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([pdf_url, status, time.strftime("%Y-%m-%d %H:%M:%S")])

class Crawler:
    def __init__(self, config):
        self.config = config
        self.logging_manager = LoggingManager()
        self.selenium_handler = SeleniumHandler(self.config)
        self.captcha_handler = CaptchaHandler(self.selenium_handler)
        self.pdf_downloader = PDFDownloader(self.config, self.logging_manager)
        self.visited_urls = self.load_resume_state()

    def load_resume_state(self):
        if os.path.exists(self.config.RESUME_STATE_FILE):
            with open(self.config.RESUME_STATE_FILE, 'rb') as f:
                return pickle.load(f)
        return set()

    def save_resume_state(self):
        with open(self.config.RESUME_STATE_FILE, 'wb') as f:
            pickle.dump(self.visited_urls, f)

    def crawl(self):
        try:
            self.selenium_handler.get_page(self.config.SEARCH_URL)
            self.captcha_handler.handle_captcha()
            pdf_urls = self.extract_pdf_urls()
            self.pdf_downloader.download_pdfs(pdf_urls)
        except Exception as e:
            self.logging_manager.log(f"Error during crawling: {e}", logging.ERROR)
        finally:
            self.save_resume_state()
            self.selenium_handler.quit()

    def extract_pdf_urls(self):
        # Logic to extract PDF URLs goes here
        pass

def main():
    config = Config()
    crawler = Crawler(config)
    crawler.crawl()

if __name__ == "__main__":
    main()
