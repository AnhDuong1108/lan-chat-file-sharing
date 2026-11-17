
import logging
import queue
from logging.handlers import QueueHandler, QueueListener


def setup_logging():
    """Configure centralized logging using a queue."""

    log_queue = queue.Queue()

    # Handler chịu trách nhiệm ghi log ra terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(formatter)

    # Các thread chỉ gửi log vào queue
    queue_handler = QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Tránh đăng ký QueueHandler nhiều lần
    root_logger.handlers.clear()
    root_logger.addHandler(queue_handler)

    # Một listener duy nhất xử lý log
    listener = QueueListener(
        log_queue,
        console_handler,
        respect_handler_level=True
    )

    listener.start()

    return listener
