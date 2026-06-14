import gc
import io
import sys

from launch.utilities import logger as logger_module


class FakeStdout:
    def __init__(self):
        self.buffer = io.BytesIO()
        self.encoding = "utf-8"
        self.errors = "replace"

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


def _drop_shared_console_without_closing_buffer() -> None:
    console = getattr(logger_module, "_shared_console", None)
    stream = getattr(console, "file", None)
    if stream is not None and hasattr(stream, "detach"):
        try:
            stream.detach()
        except (ValueError, OSError, io.UnsupportedOperation):
            pass

    if hasattr(logger_module, "_shared_console"):
        logger_module._shared_console = None


def test_repeated_console_logger_setup_keeps_stdout_buffer_open(
    tmp_path, monkeypatch
):
    '''
    Issue #30
    FAIL_TO_PASS at PR#31
    '''
    logger_name = "test_repeated_console_logger_setup"
    fake_stdout = FakeStdout()

    _drop_shared_console_without_closing_buffer()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    try:
        setup_logger = logger_module.setup_logger(
            logger_name, tmp_path / "setup.log", printing=True
        )
        setup_logger.info("setup stage")
        logger_module.clean_logger(setup_logger)
        del setup_logger
        gc.collect()

        assert not fake_stdout.buffer.closed

        organize_logger = logger_module.setup_logger(
            logger_name, tmp_path / "organize.log", printing=True
        )
        organize_logger.info("organize stage")
        logger_module.clean_logger(organize_logger)
        del organize_logger
        gc.collect()

        assert not fake_stdout.buffer.closed
    finally:
        logger_module.clean_logger(logger_name)
        _drop_shared_console_without_closing_buffer()
