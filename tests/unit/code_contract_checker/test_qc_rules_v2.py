"""Behavior tests for the six new QC rules + gate + hybrid channels (design §7)."""

from __future__ import annotations

from sanityops_cli.code_contract_checker.checker import CodeContractChecker
from sanityops_cli.code_contract_checker.models import (
    DefectStatus,
    GateResult,
    QCRuleID,
    Severity,
)
from sanityops_cli.code_contract_checker.rules import (
    check_qc_0_4_fence_integrity,
    check_qc_0_5_language_content_mismatch,
    check_qc_1_2_invalid_import,
    check_qc_1_3_deprecated_api,
    check_qc_4_1_snippet_artifact_mismatch,
    check_qc_4_2_snippet_body_drift,
)


def artifact(artifact_type: str = "prompt"):
    from sanityops_cli.code_contract_checker.models import QCArtifactResult

    return QCArtifactResult(
        artifact_type=artifact_type,
        artifact_path="/tmp/x",
        artifact_name="x",
        checked_at="now",
    )


def by_rule(result, rule_id: QCRuleID):
    return [d for d in result.defects if d.rule_id == rule_id]


class TestQc04FenceIntegrity:
    def test_unclosed_fence_flagged(self):
        result = artifact()
        check_qc_0_4_fence_integrity("prose\n```python\nprint(1)\n", result, "$.content")
        (defect,) = by_rule(result, QCRuleID.QC_0_4)
        assert defect.severity == Severity.P1
        assert "never closed" in defect.description

    def test_short_closing_fence_flagged_once(self):
        result = artifact()
        content = "```python\nprint(1)\n``\nprose after\n"
        check_qc_0_4_fence_integrity(content, result, "$.content")
        assert len(by_rule(result, QCRuleID.QC_0_4)) == 1

    def test_wellformed_document_clean(self):
        result = artifact()
        content = "intro\n\n```python\nprint(1)\n```\n\noutro\n```bash\necho hi\n```\n"
        check_qc_0_4_fence_integrity(content, result, "$.content")
        assert by_rule(result, QCRuleID.QC_0_4) == []

    def test_nested_fence_inside_4_backtick_opener_is_content(self):
        result = artifact()
        content = "````markdown\n```python\nprint(1)\n```\n````\n"
        check_qc_0_4_fence_integrity(content, result, "$.content")
        assert by_rule(result, QCRuleID.QC_0_4) == []

    def test_inline_double_backtick_not_a_fence(self):
        result = artifact()
        check_qc_0_4_fence_integrity(
            "use ``code`` inline\nand ```x``` spans\n", result, "$.content"
        )
        assert by_rule(result, QCRuleID.QC_0_4) == []


class TestQc05LanguageContentMismatch:
    def test_bash_content_in_python_fence_is_candidate(self):
        result = artifact()
        code = "echo 'installing'\napt-get install -y curl\n$(pwd)\n"
        check_qc_0_5_language_content_mismatch(code, "python", result, "$.c[0]", 10)
        (defect,) = by_rule(result, QCRuleID.QC_0_5)
        assert defect.status == DefectStatus.CANDIDATE
        assert defect.severity == Severity.P2
        assert defect.model_prompt and "bash" in defect.model_prompt

    def test_python_content_in_python_fence_clean(self):
        result = artifact()
        code = "def run():\n    print('hi')\n    return True\n"
        check_qc_0_5_language_content_mismatch(code, "python", result, "$.c[0]", 1)
        assert by_rule(result, QCRuleID.QC_0_5) == []

    def test_matching_language_clean(self):
        result = artifact()
        code = "echo 'installing'\napt-get install -y curl\n"
        check_qc_0_5_language_content_mismatch(code, "bash", result, "$.c[0]", 1)
        assert by_rule(result, QCRuleID.QC_0_5) == []

    def test_unprofiled_declared_language_skipped(self):
        result = artifact()
        check_qc_0_5_language_content_mismatch("echo hi", "text", result, "$.c[0]", 1)
        assert by_rule(result, QCRuleID.QC_0_5) == []

    def test_json_declared_with_json_content_clean(self):
        result = artifact()
        code = '{\n  "name": "x",\n  "n": 1\n}\n'
        check_qc_0_5_language_content_mismatch(code, "json", result, "$.c[0]", 1)
        assert by_rule(result, QCRuleID.QC_0_5) == []


class TestQc12InvalidImport:
    def test_stdlib_imports_clean(self):
        result = artifact()
        check_qc_1_2_invalid_import("import json, os\n", "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_1_2) == []

    def test_unknown_import_without_deps_not_executed(self):
        result = artifact()
        check_qc_1_2_invalid_import("import custom_module\n", "python", result, "$.c", 1)
        (defect,) = by_rule(result, QCRuleID.QC_1_2)
        assert defect.status == DefectStatus.NOT_EXECUTED
        assert result.not_executed_rules[QCRuleID.QC_1_2]

    def test_declared_dependency_resolves(self):
        result = artifact()
        check_qc_1_2_invalid_import(
            "import custom_module\n",
            "python",
            result,
            "$.c",
            1,
            declared_dependencies=["custom_module"],
        )
        assert by_rule(result, QCRuleID.QC_1_2) == []

    def test_unknown_import_with_deps_is_definitive_fail(self):
        result = artifact()
        check_qc_1_2_invalid_import(
            "import requests\n", "python", result, "$.c", 1, declared_dependencies=["flask"]
        )
        (defect,) = by_rule(result, QCRuleID.QC_1_2)
        assert defect.status == DefectStatus.DEFINITIVE
        assert defect.severity == Severity.P2

    def test_non_python_skipped(self):
        result = artifact()
        check_qc_1_2_invalid_import("import x", "bash", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_1_2) == []


class TestQc13DeprecatedApi:
    def test_deprecated_call_is_candidate(self):
        result = artifact()
        check_qc_1_3_deprecated_api("df = df.append(row)\n", "python", result, "$.c", 1)
        (defect,) = by_rule(result, QCRuleID.QC_1_3)
        assert defect.status == DefectStatus.CANDIDATE
        assert defect.model_prompt
        assert QCRuleID.QC_1_3 in result.not_executed_rules

    def test_partial_coverage_declared_even_when_clean(self):
        result = artifact()
        check_qc_1_3_deprecated_api("print('ok')\n", "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_1_3) == []
        assert QCRuleID.QC_1_3 in result.not_executed_rules

    def test_removed_stdlib_api_distutils(self):
        result = artifact()
        check_qc_1_3_deprecated_api("from distutils.util import x\n", "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_1_3)


class TestQc41SnippetArtifactMismatch:
    OWNER = {
        "properties": {"file_path": {"type": "string"}, "pages": {"type": "array"}},
        "required": ["file_path"],
    }

    def test_unknown_param_flagged(self):
        result = artifact()
        code = "extract(file_path='a.pdf', page=3)\n"
        check_qc_4_1_snippet_artifact_mismatch(
            code, "python", result, "$.c", 1, owner_context=self.OWNER
        )
        (defect,) = by_rule(result, QCRuleID.QC_4_1)
        assert defect.status == DefectStatus.CANDIDATE
        assert defect.severity == Severity.P1
        assert "page" in defect.description

    def test_missing_required_flagged(self):
        result = artifact()
        code = "extract(pages=[1, 2])\n"
        check_qc_4_1_snippet_artifact_mismatch(
            code, "python", result, "$.c", 1, owner_context=self.OWNER
        )
        descriptions = [d.description for d in by_rule(result, QCRuleID.QC_4_1)]
        assert any("file_path" in d for d in descriptions)

    def test_matching_snippet_clean(self):
        result = artifact()
        code = "extract(file_path='a.pdf', pages=[1])\n"
        check_qc_4_1_snippet_artifact_mismatch(
            code, "python", result, "$.c", 1, owner_context=self.OWNER
        )
        assert by_rule(result, QCRuleID.QC_4_1) == []

    def test_no_owner_context_skips(self):
        result = artifact()
        check_qc_4_1_snippet_artifact_mismatch("x=1\n", "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_4_1) == []


class TestQc42SnippetBodyDrift:
    def test_version_pin_conflict(self):
        result = artifact()
        body = "Requires requests==2.28.0 installed.\n"
        code = "pip install requests==2.31.0\n"
        check_qc_4_2_snippet_body_drift(code, "bash", result, "$.c", 1, artifact_body=body)
        (defect,) = by_rule(result, QCRuleID.QC_4_2)
        assert defect.status == DefectStatus.CANDIDATE
        assert "2.28.0" in defect.description

    def test_api_replacement_drift(self):
        result = artifact()
        body = "Use `pdfplumber.open()` instead of `pdfplumber.load()`.\n"
        code = "pdf = pdfplumber.load('f.pdf')\n"
        check_qc_4_2_snippet_body_drift(code, "python", result, "$.c", 1, artifact_body=body)
        (defect,) = by_rule(result, QCRuleID.QC_4_2)
        assert "pdfplumber.load" in defect.description

    def test_consistent_snippet_clean(self):
        result = artifact()
        body = "Requires requests==2.28.0.\nUse `pdfplumber.open()`.\n"
        code = "import requests\npdf = pdfplumber.open('f.pdf')\n"
        check_qc_4_2_snippet_body_drift(code, "python", result, "$.c", 1, artifact_body=body)
        assert by_rule(result, QCRuleID.QC_4_2) == []

    def test_no_body_skips(self):
        result = artifact()
        check_qc_4_2_snippet_body_drift("x=1\n", "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_4_2) == []


class TestGateAndExemption:
    def test_qc0_p0_blocks_qc1_4(self):
        """A syntax-broken snippet must not also emit QC-1..4 findings."""
        checker = CodeContractChecker(declared_dependencies=["flask"])
        code = "def broken(:\n    import requests\n"
        result = artifact()
        checker._run_qc_checks(code, "python", result, "$.c", 1)
        assert by_rule(result, QCRuleID.QC_0_1)
        # gate: no QC-1/2/3 rules ran (0.1/0.3/1.x/2.x/3.x absent besides 0.x)
        assert not by_rule(result, QCRuleID.QC_1_1)
        assert not by_rule(result, QCRuleID.QC_1_2)
        assert not by_rule(result, QCRuleID.QC_1_3)
        assert not by_rule(result, QCRuleID.QC_3_2)

    def test_illustrative_snippet_exempt_from_qc01_03(self):
        checker = CodeContractChecker()
        code = "def partial(...):\n    ...\n"
        result = artifact()
        checker._run_qc_checks(code, "python", result, "$.c", 1, illustrative=True)
        assert by_rule(result, QCRuleID.QC_0_1) == []
        assert by_rule(result, QCRuleID.QC_0_3) == []

    def test_extract_marks_illustrative_blocks(self):
        from sanityops_cli.code_contract_checker.rules import extract_code_blocks

        content = "```python example\ndef f():\n    ...\n```\n"
        blocks = extract_code_blocks(content, artifact(), "$")
        assert blocks[0].illustrative is True

        content_plain = "```python\ndef f():\n    ...\n```\n"
        blocks = extract_code_blocks(content_plain, artifact(), "$")
        assert blocks[0].illustrative is True  # bare ... line

        content_real = "```python\nprint(1)\n```\n"
        blocks = extract_code_blocks(content_real, artifact(), "$")
        assert blocks[0].illustrative is False

    def test_candidate_only_result_never_fails_gate(self, tmp_path):
        tool = tmp_path / "extractor.json"
        tool.write_text(
            """{
  "name": "extractor",
  "description": "Extracts pages.",
  "parameters": {
    "type": "object",
    "properties": {
      "file_path": {
        "type": "string",
        "description": "PDF path. Example:\\n```python\\nextract(file_path='a.pdf', page=3)\\n```"
      }
    },
    "required": ["file_path"]
  }
}""",
            encoding="utf-8",
        )
        checker = CodeContractChecker()
        result = checker.check_from_paths(prompts=[], tools=[str(tool)], skills=[])
        assert result.candidate_count == 1
        assert result.p0_count == 0
        assert result.gate_result == GateResult.PASS
        candidate = next(d for d in result.tools[0].defects if d.rule_id == QCRuleID.QC_4_1)
        assert candidate.status == DefectStatus.CANDIDATE
        assert candidate.model_prompt

    def test_end_to_end_finds_new_rules(self, tmp_path):
        prompt = tmp_path / "guide.md"
        prompt.write_text(
            "# Guide\n"
            "```python\nimport custom_module\ndf = df.append(x)\n"
            "conn = get_conn()\n```\n",
            encoding="utf-8",
        )
        checker = CodeContractChecker()
        result = checker.check_from_paths(prompts=[str(prompt)], tools=[], skills=[])
        defects = result.prompts[0].defects
        rule_ids = {d.rule_id for d in defects}
        assert QCRuleID.QC_1_2 in rule_ids  # unknown import → Not Executed entry
        assert QCRuleID.QC_1_3 in rule_ids  # df.append → Candidate
        statuses = {d.status for d in defects if d.rule_id == QCRuleID.QC_1_2}
        assert DefectStatus.NOT_EXECUTED in statuses
