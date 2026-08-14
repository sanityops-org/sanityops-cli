"""Unit tests for the Logger class."""

from datetime import date
from pathlib import Path

from sanityops_cli.logging.logger import Logger


class TestLogger:
    def test_creates_log_file_in_dir(self, tmp_path: Path):
        logger = Logger(tmp_path)
        assert logger.get_log_path().exists()
        assert logger.get_log_path().parent == tmp_path

    def test_filename_contains_today_date(self, tmp_path: Path):
        logger = Logger(tmp_path)
        assert logger.get_log_path().name == f"sanityops-cli-{date.today().isoformat()}.log"

    def test_creates_nested_log_dir(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "logs"
        Logger(nested)
        assert nested.is_dir()

    def test_leveled_messages_written(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.debug("debug line")
        logger.info("info line")
        logger.warning("warning line")
        logger.error("error line")
        content = logger.get_log_path().read_text()
        assert "[DEBUG] debug line" in content
        assert "[INFO] info line" in content
        assert "[WARNING] warning line" in content
        assert "[ERROR] error line" in content

    def test_step_helpers_write_expected_messages(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.step_started("Analyzing artifacts...")
        logger.step_completed("Analyzing artifacts...", 1.234)
        logger.step_failed("Analyzing artifacts...", "boom")
        content = logger.get_log_path().read_text()
        assert "[INFO] Step started: Analyzing artifacts..." in content
        assert "[INFO] Step completed: Analyzing artifacts... (1.23s)" in content
        assert "[ERROR] Step failed: Analyzing artifacts... - boom" in content

    def test_redact_masks_api_key_values(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.info("using api_key=sk-abc123DEF456 token")
        logger.info("auth: sk-proj-9f8e7d6c5b4a3a")
        content = logger.get_log_path().read_text()
        assert "sk-abc123DEF456" not in content
        assert "sk-proj-9f8e7d6c5b4a3a" not in content
        assert "api_key=***" in content
        assert "sk-***" in content

    def test_redact_masks_value_with_backslash(self, tmp_path: Path):
        # regression: values containing backslashes must still be redacted
        # (the api_key pattern uses [^\s\"',}]+ — the escaped quote does not
        # exclude backslashes from the match)
        logger = Logger(tmp_path)
        logger.info("using api_key=sk-abc\\def token")
        content = logger.get_log_path().read_text()
        assert "api_key=***" in content
        assert "sk-abc" not in content

    def test_redact_static(self):
        assert "sk-***" in Logger.redact("key=sk-abcdefghijklmn")
        assert Logger.redact("plain message") == "plain message"

    def test_close_removes_handlers(self, tmp_path: Path):
        logger = Logger(tmp_path)
        assert logger._logger.handlers
        logger.close()
        assert logger._logger.handlers == []

    def test_close_is_idempotent(self, tmp_path: Path):
        logger = Logger(tmp_path)
        logger.close()
        logger.close()  # second close must not raise
        assert logger._logger.handlers == []
