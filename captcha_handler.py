import os
import time
import requests
from selenium_handler import SeleniumHandler
from logging_manager import LoggingManager, ErrorType
from config import Config

class CaptchaHandler:
    def __init__(self, config: Config, selenium_handler: SeleniumHandler, logging_manager: LoggingManager):
        self.config = config
        self.selenium_handler = selenium_handler
        self.logging_manager = logging_manager
        self.captcha_image_path = os.path.join(self.config.get_directory("pdf_dir"), self.config.files["captcha_image"])
        self.max_retries = self.config.misc_settings.get("max_retries", 3)
        self.ai_service_url = self.config.misc_settings.get("ai_captcha_service_url", "")
        self.ai_service_api_key = self.config.misc_settings.get("ai_captcha_service_api_key", "")

    def fetch_captcha_file(self):
        """Fetches the CAPTCHA image from the website and saves it locally."""
        try:
            self.logging_manager.log_info("Fetching CAPTCHA image...")
            captcha_element = self.selenium_handler.wait_for_element(self.config.get_html_element("captcha_id"))
            captcha_src = captcha_element.get_attribute("src")
            
            captcha_img = requests.get(captcha_src, stream=True)
            
            if captcha_img.status_code == 200:
                with open(self.captcha_image_path, 'wb') as f:
                    f.write(captcha_img.content)
                self.logging_manager.log_info(f"CAPTCHA image saved to {self.captcha_image_path}")
            else:
                raise Exception(f"Failed to fetch CAPTCHA image. Status code: {captcha_img.status_code}")
        except Exception as e:
            self.logging_manager.log_error(f"Error fetching CAPTCHA: {str(e)}", ErrorType.NETWORK)
            raise

    def solve_captcha_manually(self):
        """Pauses the script to allow manual CAPTCHA solving."""
        self.logging_manager.log_info("Waiting for manual CAPTCHA solving...")
        captcha_solution = input("Please solve the CAPTCHA manually and enter the solution: ")
        return captcha_solution.strip()

    def solve_captcha_with_ai(self):
        """Tries to solve the CAPTCHA using an AI-based solution."""
        if not self.ai_service_url or not self.ai_service_api_key:
            self.logging_manager.log_warning("AI CAPTCHA service not configured. Falling back to manual solving.")
            return self.solve_captcha_manually()
        
        try:
            self.logging_manager.log_info("Attempting to solve CAPTCHA with AI...")
            with open(self.captcha_image_path, 'rb') as image_file:
                files = {'image': image_file}
                headers = {'Authorization': f'Bearer {self.ai_service_api_key}'}
                response = requests.post(self.ai_service_url, files=files, headers=headers)
            
            if response.status_code == 200:
                captcha_solution = response.json().get('solution')
                if captcha_solution:
                    self.logging_manager.log_info("CAPTCHA solved successfully using AI.")
                    return captcha_solution
                else:
                    raise Exception("AI service did not return a solution.")
            else:
                raise Exception(f"AI service returned status code: {response.status_code}")
        except Exception as e:
            self.logging_manager.log_error(f"Failed to solve CAPTCHA with AI: {str(e)}", ErrorType.NETWORK)
            raise

    def enter_captcha_solution(self, solution):
        """Enters the CAPTCHA solution into the appropriate field."""
        try:
            self.selenium_handler.fill_input_field(self.config.get_html_element("captcha_input_id"), solution)
            self.selenium_handler.submit_form(self.config.get_html_element("submit_button_xpath"))
            
            # Wait for the result of CAPTCHA submission
            time.sleep(self.config.misc_settings.get("retry_delay", 5))
            
            if "Invalid CAPTCHA" in self.selenium_handler.driver.page_source:
                self.logging_manager.log_warning("CAPTCHA solution incorrect.")
                return False
            return True
        except Exception as e:
            self.logging_manager.log_error(f"Error entering CAPTCHA solution: {str(e)}", ErrorType.PARSING)
            return False

    def clean_up_captcha_file(self):
        """Deletes the CAPTCHA image after the attempt."""
        try:
            if os.path.exists(self.captcha_image_path):
                os.remove(self.captcha_image_path)
                self.logging_manager.log_info(f"Deleted CAPTCHA image: {self.captcha_image_path}")
            else:
                self.logging_manager.log_warning(f"CAPTCHA image not found for deletion: {self.captcha_image_path}")
        except Exception as e:
            self.logging_manager.log_error(f"Error deleting CAPTCHA image: {str(e)}", ErrorType.FILE_IO)

    def solve_captcha(self, tries_remaining):
        """Attempts to solve the CAPTCHA based on the number of retries left."""
        try:
            self.fetch_captcha_file()

            if tries_remaining == 1:
                self.logging_manager.log_info("One try remaining. Resorting to manual CAPTCHA solving.")
                solution = self.solve_captcha_manually()
            else:
                self.logging_manager.log_info(f"Tries remaining: {tries_remaining}. Attempting AI CAPTCHA solving.")
                try:
                    solution = self.solve_captcha_with_ai()
                except Exception:
                    if tries_remaining - 1 > 0:
                        return self.solve_captcha(tries_remaining - 1)
                    else:
                        solution = self.solve_captcha_manually()

            if self.enter_captcha_solution(solution):
                self.logging_manager.log_info("CAPTCHA solved successfully.")
                return True
            else:
                if tries_remaining > 1:
                    return self.solve_captcha(tries_remaining - 1)
                return False

        finally:
            self.clean_up_captcha_file()

    def start_captcha_process(self):
        """Initiates the CAPTCHA-solving process with retries from the config."""
        self.logging_manager.log_info(f"Starting CAPTCHA process with max retries: {self.max_retries}")
        return self.solve_captcha(self.max_retries)

# Example usage
if __name__ == "__main__":
    config = Config()
    logging_manager = LoggingManager(config)

    if logging_manager.validate_config():
        with SeleniumHandler(config, logging_manager) as selenium_handler:
            selenium_handler.driver.get(config.get_link("search_url"))
            captcha_handler = CaptchaHandler(config, selenium_handler, logging_manager)
            
            try:
                if captcha_handler.start_captcha_process():
                    logging_manager.log_step(["CAPTCHA", "Success"], is_successful=True)
                    print("CAPTCHA solved successfully. Proceeding with search...")
                else:
                    logging_manager.log_step(["CAPTCHA", "Failed"], is_successful=False)
                    print("Failed to solve CAPTCHA. Aborting search process.")
            except Exception as e:
                logging_manager.log_error(f"Unexpected error during CAPTCHA handling: {str(e)}", ErrorType.UNKNOWN)
    else:
        print("Configuration validation failed. Please check your config file.")