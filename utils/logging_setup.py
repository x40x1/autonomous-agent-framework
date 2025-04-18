import logging
import sys

def setup_logging(level=logging.INFO):
    """Configures the root logger."""
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format)

    # Console handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)

    # File handler (enabled by default for debugging)
    file_handler = logging.FileHandler("agent_run.log")
    file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set root logger to DEBUG to catch all messages

    # Clear existing handlers to avoid duplicates if called multiple times
    root_logger.handlers.clear()

    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)  # Always add file handler for debugging

    # Ensure tools module logs at DEBUG level
    logging.getLogger("tools").setLevel(logging.DEBUG)

    # Suppress noisy libraries if needed
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    logging.info("Logging configured with root level DEBUG and console level {}.".format(
        "DEBUG" if level == logging.DEBUG else "INFO"
    ))

if __name__ == '__main__':
    setup_logging(logging.DEBUG)
    logging.debug("Debug message")
    logging.info("Info message")
    logging.warning("Warning message")
    logging.error("Error message")
    logging.critical("Critical message")