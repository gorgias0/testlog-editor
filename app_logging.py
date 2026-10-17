import logging
import logging.handlers
import os
import sys
import threading

from PySide6.QtCore import QStandardPaths


LOGGER_NAME = "testlog"
LOG_FILENAME = "testlog-editor.log"


def setup_logging():
    # Call after QApplication has its organization and application names, since the
    # log folder is derived from them. Logging must never stop the app from starting.
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    log_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    if not log_dir:
        return None
    log_path = os.path.join(log_dir, LOG_FILENAME)
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        logger.warning("Could not open log file %s; logging to stderr only", log_path, exc_info=True)
        return None
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return log_path


def install_excepthook(show_error, log_path):
    # PySide6 hands exceptions raised inside slots to sys.excepthook, so this covers
    # timers, menu actions and buttons as well as startup code.
    logger = logging.getLogger(LOGGER_NAME)
    showing = False

    def handle(exc_type, exc, tb):
        nonlocal showing
        logger.error("Unhandled exception", exc_info=(exc_type, exc, tb))
        if showing:
            return
        showing = True
        try:
            show_error(log_path)
        except Exception:
            logger.error("Could not show the error dialog", exc_info=True)
        finally:
            showing = False

    def handle_thread(args):
        logger.error(
            "Unhandled exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle
    threading.excepthook = handle_thread
