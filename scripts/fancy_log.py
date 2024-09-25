import logging
import time

from colorama import Fore, Style


class FancyFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }
    OTHER_COLORS = {
        "time": Fore.MAGENTA,
        "name": Fore.CYAN,
        "filename": Fore.CYAN,
        "lineno": Fore.CYAN,
    }
    BASE_COLOR = Fore.WHITE

    def format(self, record):
        level_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        formatted_log = (
            f"{self.BASE_COLOR}Level: {level_color}{record.levelname}{Style.RESET_ALL}\n"
            f"{self.BASE_COLOR}Time: {self.OTHER_COLORS["time"]}{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}{Style.RESET_ALL}\n"
            f"{level_color}Logger: {record.name}{Style.RESET_ALL}\n"
            f"{level_color}File: {record.filename}{Style.RESET_ALL}\n"
            f"{level_color}Line: {record.lineno}{Style.RESET_ALL}\n"
            f"{level_color}Message: {record.getMessage()}{Style.RESET_ALL}\n"
        )
        return formatted_log


class FancyHandler(logging.StreamHandler):
    def emit(self, record):
        msg = self.format(record)
        print(msg)


class CustomLogger:
    _loggers = {}
    _level = logging.DEBUG
    _formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    _handlers = [logging.StreamHandler()]

    @classmethod
    def init(cls, level=logging.DEBUG, formatter=None, handlers=None):
        """
        Initializes the custom logger configuration.

        :param level: Logging level.
        :param formatter: Formatter to use for the log messages.
        :param handlers: List of handlers to add to the logger.
        """
        cls._level = level

        # Use a custom formatter if provided
        if formatter is not None:
            cls._formatter = formatter

        # Use custom handlers if provided
        if handlers is not None:
            cls._handlers = handlers

    @classmethod
    def set_level(cls, level):
        """
        Sets the logging level for the logger.

        :param level: Logging level.
        """
        cls._level = level

    @classmethod
    def get_logger(cls, name):
        """
        Returns a logger instance with the specified name.

        :param name: Name of the logger (usually the module's __name__).
        :return: Logger instance.
        """
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(cls._level)
            for handler in cls._handlers:
                handler.setFormatter(cls._formatter)
                logger.addHandler(handler)
            cls._loggers[name] = logger
        return cls._loggers[name]


class FancyLogger(CustomLogger):
    _formatter = FancyFormatter()
    _handlers = [FancyHandler()]


if __name__ == "__main__":
    # Set up logging
    # logger = logging.getLogger("custom_logger")
    # logger.setLevel(logging.DEBUG)

    # # Console handler with custom formatter
    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(FancyFormatter())

    # # Adding handler to logger
    # logger.addHandler(console_handler)

    # # Example log messages
    # logger.debug("This is a debug message")
    # logger.info("This is an info message")
    # logger.warning("This is a warning message")
    # logger.error("This is an error message")
    # logger.critical("This is a critical message")

    logger = FancyLogger.get_logger("fancy_log")
    logger.setLevel(logging.DEBUG)

    logger.debug("This is a debug message")
    logger.info("This is an info message")
