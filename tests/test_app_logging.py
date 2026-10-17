import logging
import sys
import threading

import pytest
from PySide6.QtCore import QStandardPaths

import app_logging


@pytest.fixture
def clean_logger(monkeypatch):
    logger = logging.getLogger(app_logging.LOGGER_NAME)
    handlers = list(logger.handlers)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    yield logger
    for handler in logger.handlers:
        if handler not in handlers:
            handler.close()
    logger.handlers = handlers


def _raise_and_capture():
    try:
        raise ZeroDivisionError("boom")
    except ZeroDivisionError:
        return sys.exc_info()


def test_setup_logging_writes_to_app_data_folder(tmp_path, monkeypatch, clean_logger):
    log_dir = tmp_path / "app data"
    monkeypatch.setattr(QStandardPaths, "writableLocation", staticmethod(lambda location: str(log_dir)))

    log_path = app_logging.setup_logging()
    clean_logger.warning("hello from test")
    for handler in clean_logger.handlers:
        handler.flush()

    assert log_path == str(log_dir / app_logging.LOG_FILENAME)
    assert "hello from test" in (log_dir / app_logging.LOG_FILENAME).read_text(encoding="utf-8")


def test_setup_logging_falls_back_when_folder_cannot_be_created(tmp_path, monkeypatch, clean_logger):
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(QStandardPaths, "writableLocation", staticmethod(lambda location: str(blocker / "logs")))

    assert app_logging.setup_logging() is None


def test_excepthook_logs_and_shows_error_once_per_exception(caplog, clean_logger):
    shown = []
    app_logging.install_excepthook(shown.append, "/logs/testlog-editor.log")

    with caplog.at_level(logging.ERROR, logger=app_logging.LOGGER_NAME):
        sys.excepthook(*_raise_and_capture())

    assert shown == ["/logs/testlog-editor.log"]
    assert "ZeroDivisionError: boom" in caplog.text


def test_excepthook_does_not_recurse_when_dialog_raises(caplog, clean_logger):
    calls = []

    def show_error(log_path):
        calls.append(log_path)
        sys.excepthook(*_raise_and_capture())
        raise RuntimeError("dialog failed")

    app_logging.install_excepthook(show_error, None)
    with caplog.at_level(logging.ERROR, logger=app_logging.LOGGER_NAME):
        sys.excepthook(*_raise_and_capture())

    assert calls == [None]
    assert "Could not show the error dialog" in caplog.text


def test_thread_exceptions_are_logged(caplog, clean_logger):
    app_logging.install_excepthook(lambda log_path: None, None)

    def fail():
        raise ValueError("in thread")

    with caplog.at_level(logging.ERROR, logger=app_logging.LOGGER_NAME):
        thread = threading.Thread(target=fail, name="indexer")
        thread.start()
        thread.join()

    assert "Unhandled exception in thread indexer" in caplog.text
    assert "ValueError: in thread" in caplog.text
