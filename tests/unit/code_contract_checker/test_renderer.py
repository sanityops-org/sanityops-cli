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

"""Tests for QCRenderer terminal output."""

from rich.console import Console

from sanityops_cli.code_contract_checker.models import QCArtifactResult, QCInspectionResult
from sanityops_cli.code_contract_checker.renderer import QCRenderer


def _artifact() -> QCArtifactResult:
    return QCArtifactResult(
        artifact_type="prompt",
        artifact_path="/tmp/p.md",
        artifact_name="p.md",
    )


class TestQCRenderer:
    def test_summary_table_rendered(self):
        console = Console(record=True, width=80)
        result = QCInspectionResult(prompts=[_artifact()])
        QCRenderer(console).render(result)
        out = console.export_text()
        assert "Code Contract Inspection Summary" in out
        assert "QC Gate" in out

    def test_pass_gate_footer(self):
        console = Console(record=True, width=80)
        result = QCInspectionResult(prompts=[_artifact()])
        QCRenderer(console).render(result)
        out = console.export_text()
        assert "PASS" in out

    def test_fail_gate_shows_red(self):
        console = Console(record=True, width=80)
        artifact = _artifact()
        from sanityops_cli.code_contract_checker.rules import (
            check_qc_0_1_syntax_parsability,
        )

        check_qc_0_1_syntax_parsability("def f(:\n", "python", artifact, "$.c", 0)
        result = QCInspectionResult(prompts=[artifact])
        QCRenderer(console).render(result)
        out = console.export_text()
        assert "FAIL" in out

    def test_defect_details_rendered(self):
        console = Console(record=True, width=80)
        artifact = _artifact()
        from sanityops_cli.code_contract_checker.rules import (
            check_qc_1_1_undefined_name,
        )

        check_qc_1_1_undefined_name("x = missing_name\n", "python", artifact, "$.c", 0)
        result = QCInspectionResult(prompts=[artifact])
        QCRenderer(console).render(result)
        out = console.export_text()
        assert "missing_name" in out
        assert "QC-1.1" in out
