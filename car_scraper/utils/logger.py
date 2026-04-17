import logging
import sys
import os

# Create standard log directories if they don't exist
os.makedirs("logs", exist_ok=True)

class SiteLogFormatter(logging.Formatter):
    """Custom formatter to inject the 'site' variable correctly or default it."""
    def format(self, record):
        if not hasattr(record, 'site'):
            record.site = "SYSTEM"
        return super().format(record)

class ColorFormatter(SiteLogFormatter):
    """Adds ANSI colors to terminal log output based on severity and highlights targets."""
    COLORS = {
        logging.DEBUG: '\033[90m',    # Gray
        logging.INFO: '\033[36m',     # Cyan
        logging.WARNING: '\033[93m',  # Yellow
        logging.ERROR: '\033[91m',    # Red
        logging.CRITICAL: '\033[95m'  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if not hasattr(record, 'site'):
            record.site = "SYSTEM"
            
        level_color = self.COLORS.get(record.levelno, self.RESET)
        levelname_colored = f"{level_color}{record.levelname:<8}{self.RESET}"
        
        import re
        msg = record.getMessage()
        # Highlight [make/model] style tags in bright blue
        msg_colored = re.sub(r'(\[.*?/.*?\])', f'\033[94m\\1{self.RESET}', msg)
        
        timestamp = super().formatTime(record, "%Y-%m-%d %H:%M:%S")
        
        return f"{timestamp} | {levelname_colored} | {record.site:<13} | {msg_colored}"

def setup_logger():
    logger = logging.getLogger("ScraperLogger")
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers if setup_logger is called multiple times
    if logger.handlers:
        return logger

    # Log format: [TIMESTAMP] [SITE] [STATUS] Message
    # mapped to: [%(asctime)s] [%(site)s] [%(levelname)s] %(message)s
    formatter = SiteLogFormatter("[%(asctime)s] [%(site)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # 1. Scraper Log (INFO level)
    scraper_handler = logging.FileHandler("logs/scraper_log.txt", mode='a', encoding='utf-8')
    scraper_handler.setLevel(logging.INFO)
    scraper_handler.setFormatter(formatter)
    logger.addHandler(scraper_handler)

    # 2. Error Log (ERROR level)
    error_handler = logging.FileHandler("logs/error_log.txt", mode='a', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # 3. Console Output (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColorFormatter())
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()
