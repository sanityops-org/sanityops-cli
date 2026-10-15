# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for CodeContractChecker and the QC markdown reporter."""

import json
from pathlib import Path

from sanityops_cli.code_contract_checker.checker import CodeContractChecker
from sanityops_cli.code_contract_checker.markdown_reporter import save_qc_report
from sanityops_cli.code_contract_checker.models import QCArtifactResult, QCInspectionResult


class TestCodeContractChecker:
    def test_python_source_file_flags_syntax_error(self, tmp_path: Path):
        bad = tmp_path / "bad.py"
        bad.write_text("def f(:\n", encoding="utf-8")
        result = CodeContractChecker().check_from_paths([], [str(bad)], [])
        assert result.total_defects >= 1
        assert result.p0_count == 1

    def test_markdown_prompt_code_block_checked(self, tmp_path: Path):
        prompt = tmp_path / "p.md"
        prompt.write_text(
            "# Guide\n\n```python\nx = undefined_var\n```\n",
            encoding="utf-8",
        )
        result = CodeContractChecker().check_from_paths([str(prompt)], [], [])
        assert result.prompts[0].total_defects >= 1

    def test_clean_artifact_has_no_defects(self, tmp_path: Path):
        skill = tmp_path / "SKILL.md"
        skill.write_text(
            "---\nname: ok\ndescription: clean\n---\n\n```python\ndef f(a):\n    return a\n```\n",
            encoding="utf-8",
        )
        result = CodeContractChecker().check_from_paths([], [], [str(skill)])
        assert result.total_defects == 0
        assert result.gate_result == "PASS"

    def test_unreadable_file_skipped(self, tmp_path: Path):
        result = CodeContractChecker().check_from_paths([str(tmp_path / "missing.md")], [], [])
        assert result.prompts[0].total_defects == 0

    def test_tool_json_description_code_checked(self, tmp_path: Path):
        tool = tmp_path / "tool.json"
        tool.write_text(
            json.dumps(
                {
                    "name": "t",
                    "description": "Example:\n```python\nrun(undefined_helper)\n```",
                    "parameters": {"type": "object", "properties": {}},
                }
            ),
            encoding="utf-8",
        )
        result = CodeContractChecker().check_from_paths([], [str(tool)], [])
        assert result.tools[0].total_defects >= 1

    def test_invalid_json_tool_falls_back_to_code_blocks(self, tmp_path: Path):
        tool = tmp_path / "tool.json"
        tool.write_text("```python\nx = missing_name\n```", encoding="utf-8")
        result = CodeContractChecker().check_from_paths([], [str(tool)], [])
        assert result.tools[0].total_defects >= 1

    def test_inspection_time_recorded(self, tmp_path: Path):
        prompt = tmp_path / "p.md"
        prompt.write_text("plain text", encoding="utf-8")
        result = CodeContractChecker().check_from_paths([str(prompt)], [], [])
        assert result.inspection_time_seconds >= 0

    def test_binary_file_skipped(self, tmp_path: Path):
        """A file that fails UTF-8 decoding is skipped without crashing."""
        binary = tmp_path / "b.md"
        binary.write_bytes(b"\x80\x81\x82\xff\xfe")
        result = CodeContractChecker().check_from_paths([str(binary)], [], [])
        assert result.prompts[0].total_defects == 0

    def test_empty_file_no_defects(self, tmp_path: Path):
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")
        result = CodeContractChecker().check_from_paths([str(empty)], [], [])
        assert result.prompts[0].total_defects == 0


class TestSaveQcReport:
    def _qc_result(self) -> QCInspectionResult:
        artifact = QCArtifactResult(
            artifact_type="prompt",
            artifact_path="/tmp/p.md",
            artifact_name="p.md",
        )
        return QCInspectionResult(prompts=[artifact])

    def test_report_written(self, tmp_path: Path):
        path = save_qc_report(self._qc_result(), tmp_path, project_id="p1")
        assert path is not None and path.exists()
        text = path.read_text(encoding="utf-8")
        assert "# Code Contract Inspection Report" in text
        assert "## Summary" in text
        assert "## Rule Reference" in text
        assert "p1" in text

    def test_report_includes_defects_table(self, tmp_path: Path):
        qc = self._qc_result()
        qc.prompts[0].defects = []
        # Inject one defect via the rule to keep the model authoritative
        from sanityops_cli.code_contract_checker.rules import (
            check_qc_0_1_syntax_parsability,
        )

        check_qc_0_1_syntax_parsability("def f(:\n", "python", qc.prompts[0], "$.c", 0)
        path = save_qc_report(qc, tmp_path)
        assert path is not None
        text = path.read_text(encoding="utf-8")
        assert "QC-0.1" in text

    def test_report_unwritable_returns_none(self, tmp_path: Path):
        blocker = tmp_path / "file"
        blocker.write_text("not a dir", encoding="utf-8")
        path = save_qc_report(self._qc_result(), blocker)
        assert path is None
