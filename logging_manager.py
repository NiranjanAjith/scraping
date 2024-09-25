import os
import logging
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
from config import Config

class ErrorType(Enum):
    NETWORK = "Network Error"
    PARSING = "Parsing Error"
    FILE_IO = "File I/O Error"
    CONFIGURATION = "Configuration Error"
    CAPTCHA = "CAPTCHA Error"
    UNKNOWN = "Unknown Error"

class LoggingManager:
    def __init__(self, config: Config):
        self.config = config
        self.general_log_file = config.directories['log_file']
        self.csv_error_log_file = config.directories['csv_error_log']
        self.csv_dialect = csv.excel
        self.csv_dialect.delimiter = ','
        self.csv_dialect.quotechar = '"'
        self.csv_dialect.quoting = csv.QUOTE_MINIMAL

        self.setup_logging()
        self.init_csv_error_log()

    def setup_logging(self):
        try:
            os.makedirs(os.path.dirname(self.general_log_file), exist_ok=True)
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                handlers=[
                    logging.FileHandler(self.general_log_file),
                    logging.StreamHandler()
                ]
            )
            logging.info("General logging initialized.")

            error_handler = logging.FileHandler(self.general_log_file)
            error_handler.setLevel(logging.ERROR)
            error_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s')
            error_handler.setFormatter(error_format)

            error_logger = logging.getLogger("error_logger")
            error_logger.setLevel(logging.ERROR)
            error_logger.addHandler(error_handler)

            logging.info("Error logging initialized.")
        except Exception as e:
            print(f"Failed to setup logging: {str(e)}")
            raise

    def init_csv_error_log(self):
        try:
            os.makedirs(os.path.dirname(self.csv_error_log_file), exist_ok=True)
            if not os.path.exists(self.csv_error_log_file):
                with open(self.csv_error_log_file, mode='w', newline='') as file:
                    writer = csv.writer(file, dialect=self.csv_dialect)
                    writer.writerow(["Timestamp", "Error Type", "Error Message", "Additional Info"])
                logging.info("CSV error log initialized.")
        except IOError as e:
            logging.error(f"Failed to initialize CSV error log: {str(e)}")
            raise

    def log_error(self, message: str, error_type: ErrorType, exception: Optional[Exception] = None, additional_info: Optional[Dict[str, Any]] = None):
        timestamp = self.get_timestamp()
        logging.error(f"{error_type.value}: {message}")

        if exception:
            logging.exception("Exception details:", exc_info=exception)

        try:
            with open(self.csv_error_log_file, mode='a', newline='') as file:
                writer = csv.writer(file, dialect=self.csv_dialect)
                writer.writerow([
                    timestamp, 
                    error_type.value, 
                    message, 
                    str(additional_info) if additional_info else ""
                ])
        except IOError as e:
            logging.error(f"Failed to write to CSV error log: {str(e)}")

    def log_info(self, message: str):
        logging.info(message)

    def log_warning(self, message: str):
        logging.warning(message)

    def log_to_csv(self, file_type: str, record: List[Any]):
        csv_file = self.config.directories.get(f'{file_type}_csv')
        if not csv_file:
            self.log_error(f"Invalid CSV file type: {file_type}", ErrorType.CONFIGURATION)
            return

        try:
            with open(csv_file, mode='a', newline='') as file:
                writer = csv.writer(file, dialect=self.csv_dialect)
                writer.writerow(record)
            self.log_info(f"Updated {csv_file} with data: {record}")
        except IOError as e:
            self.log_error(f"Failed to update {csv_file}: {str(e)}", ErrorType.FILE_IO)

    def log_step(self, step_data: List[Any], is_successful: bool):
        self.log_to_csv('all', step_data)

        if is_successful:
            self.log_to_csv('good', step_data)
        else:
            self.log_to_csv('bad', step_data)

    @staticmethod
    def get_timestamp() -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def validate_logging_config(self) -> bool:
        required_keys = ['log_file', 'csv_error_log', 'all_csv', 'good_csv', 'bad_csv']
        for key in required_keys:
            if not self.config.directories.get(key):
                self.log_error(f"Missing configuration key: {key}", ErrorType.CONFIGURATION)
                return False
        return True

# Example Usage
if __name__ == "__main__":
    config = Config()
    logging_manager = LoggingManager(config)

    if logging_manager.validate_logging_config():
        try:
            # Simulate some operations and logging
            logging_manager.log_step(
                ["http://example.com", "Success", "Sample data"],
                is_successful=True
            )
            
            # Simulate a network error
            try:
                raise ConnectionError("Failed to connect to the server")
            except ConnectionError as e:
                logging_manager.log_error(
                    "Network connection failed", 
                    ErrorType.NETWORK, 
                    exception=e,
                    additional_info={"url": "http://example.com", "attempt": 1}
                )
                logging_manager.log_step(
                    ["http://example.com", "Failed", "Network error"],
                    is_successful=False
                )
        except Exception as e:
            logging_manager.log_error(f"Unexpected error occurred", ErrorType.UNKNOWN, exception=e)

        # Additional logging
        logging_manager.log_info("Crawler process completed.")
    else:
        print("Logging configuration validation failed. Please check your config file.")