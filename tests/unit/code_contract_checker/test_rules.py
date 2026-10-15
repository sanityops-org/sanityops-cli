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

"""Tests for code_contract_checker rule implementations."""

from sanityops_cli.code_contract_checker.models import QCArtifactResult, Severity
from sanityops_cli.code_contract_checker.rules import (
    check_qc_0_1_syntax_parsability,
    check_qc_0_2_language_declaration,
    check_qc_0_3_structural_completeness,
    check_qc_1_1_undefined_name,
    check_qc_1_4_type_mismatch,
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
    extract_code_blocks,
)


def _result() -> QCArtifactResult:
    return QCArtifactResult(
        artifact_type="prompt",
        artifact_path="/tmp/x.md",
        artifact_name="x.md",
    )


def _rule_ids(result: QCArtifactResult) -> list[str]:
    return [str(d.rule_id) for d in result.defects]


class TestQc01SyntaxParsability:
    def test_valid_python_no_defects(self):
        result = _result()
        check_qc_0_1_syntax_parsability("x = 1\n", "python", result, "$.c", 0)
        assert result.defects == []

    def test_syntax_error_reports_p0(self):
        result = _result()
        check_qc_0_1_syntax_parsability("def f(:\n", "python", result, "$.c", 0)
        assert len(result.defects) == 1
        assert result.defects[0].severity == Severity.P0
        assert result.defects[0].line_number == 1

    def test_non_python_language_skipped(self):
        result = _result()
        check_qc_0_1_syntax_parsability("def f(:\n", "javascript", result, "$.c", 0)
        assert result.defects == []


class TestQc02LanguageDeclaration:
    def test_missing_language_reports_p1(self):
        result = _result()
        check_qc_0_2_language_declaration(None, result, "$.c", 7)
        assert len(result.defects) == 1
        assert result.defects[0].severity == Severity.P1
        assert result.defects[0].line_number == 7

    def test_empty_language_reports_p1(self):
        result = _result()
        check_qc_0_2_language_declaration("", result, "$.c", 7)
        assert len(result.defects) == 1
        assert result.defects[0].severity == Severity.P1

    def test_whitespace_language_reports_p1(self):
        result = _result()
        check_qc_0_2_language_declaration("   ", result, "$.c", 7)
        assert len(result.defects) == 1

    def test_declared_language_no_defects(self):
        result = _result()
        check_qc_0_2_language_declaration("python", result, "$.c", 7)
        assert result.defects == []


class TestQc03StructuralCompleteness:
    def test_truncated_function_body_detected(self):
        result = _result()
        code = "def f(a, b):\n    ...\n"
        check_qc_0_3_structural_completeness(code, "python", result, "$.c", 0)
        assert "QC-0.3" in _rule_ids(result)

    def test_unclosed_bracket_detected(self):
        # A bracket left open at EOF is a syntax error, so QC-0.1 reports it
        # as a P0 defect rather than QC-0.3.
        result = _result()
        code = "x = [1, 2, 3\n"
        check_qc_0_3_structural_completeness(code, "python", result, "$.c", 0)
        # QC-0.3 skips code that fails to tokenize (QC-0.1 owns that case)
        assert result.defects == []

        from sanityops_cli.code_contract_checker.rules import (
            check_qc_0_1_syntax_parsability,
        )

        result2 = _result()
        check_qc_0_1_syntax_parsability(code, "python", result2, "$.c", 0)
        assert "QC-0.1" in _rule_ids(result2)

    def test_brackets_in_strings_ignored(self):
        result = _result()
        code = 'x = "([{"\ny = 1\n'
        check_qc_0_3_structural_completeness(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_valid_code_no_defects(self):
        result = _result()
        code = "def f(a, b):\n    return a + b\n"
        check_qc_0_3_structural_completeness(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestExtractCodeBlocks:
    def test_extracts_python_block(self):
        result = _result()
        content = "text\n\n```python\nx = 1\n```\n"
        blocks = extract_code_blocks(content, result, "$")
        assert len(blocks) == 1
        code, lang, line = blocks[0]
        assert code.strip() == "x = 1"
        assert lang == "python"
        assert line == 3

    def test_alias_normalization(self):
        result = _result()
        blocks = extract_code_blocks("```py\nx = 1\n```", result, "$")
        assert blocks[0][1] == "python"

    def test_missing_language_flags_qc02(self):
        result = _result()
        extract_code_blocks("```\nx = 1\n```", result, "$")
        assert "QC-0.2" in _rule_ids(result)


class TestQc11UndefinedName:
    def test_undefined_name_detected(self):
        result = _result()
        code = "def f():\n    return undefined_thing\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert "QC-1.1" in _rule_ids(result)

    def test_imported_name_not_flagged(self):
        result = _result()
        code = "import os\n\ndef f():\n    return os.getcwd()\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_builtin_not_flagged(self):
        result = _result()
        code = "value = len([1, 2])\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_self_and_cls_not_flagged(self):
        result = _result()
        code = "class A:\n    def m(self):\n        return self.x\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_dunder_not_flagged(self):
        result = _result()
        code = "__name__\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_loop_and_params_not_flagged(self):
        result = _result()
        code = "def f(items):\n    for item in items:\n        print(item)\n"
        check_qc_1_1_undefined_name(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc14TypeMismatch:
    def test_range_with_string_detected(self):
        result = _result()
        check_qc_1_4_type_mismatch('range("5")\n', "python", result, "$.c", 0)
        assert "QC-1.4" in _rule_ids(result)

    def test_range_with_int_ok(self):
        result = _result()
        check_qc_1_4_type_mismatch("range(5)\n", "python", result, "$.c", 0)
        assert result.defects == []


class TestQc21UnclosedFileHandle:
    def test_open_without_close_detected(self):
        result = _result()
        code = "f = open('a.txt')\nprint(f)\n"
        check_qc_2_1_unclosed_file_handle(code, "python", result, "$.c", 0)
        assert "QC-2.1" in _rule_ids(result)

    def test_with_statement_ok(self):
        result = _result()
        code = "with open('a.txt') as f:\n    print(f)\n"
        check_qc_2_1_unclosed_file_handle(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_explicit_close_ok(self):
        result = _result()
        code = "f = open('a.txt')\nf.close()\n"
        check_qc_2_1_unclosed_file_handle(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc22UnreleasedNetwork:
    def test_socket_without_close_detected(self):
        result = _result()
        code = "import socket\ns = socket.socket()\nprint(s)\n"
        check_qc_2_2_unreleased_network(code, "python", result, "$.c", 0)
        assert "QC-2.2" in _rule_ids(result)

    def test_urlopen_with_close_ok(self):
        result = _result()
        code = "import urllib.request\nr = urllib.request.urlopen('http://x')\nr.close()\n"
        check_qc_2_2_unreleased_network(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc23MissingExceptionHandling:
    def test_high_risk_call_without_try_detected(self):
        result = _result()
        code = "f = open('a.txt')\n"
        check_qc_2_3_missing_exception_handling(code, "python", result, "$.c", 0)
        assert "QC-2.3" in _rule_ids(result)

    def test_high_risk_call_in_try_ok(self):
        result = _result()
        code = "try:\n    f = open('a.txt')\nexcept OSError:\n    pass\n"
        check_qc_2_3_missing_exception_handling(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc31UnusedImport:
    def test_unused_import_detected(self):
        result = _result()
        code = "import os\n\nprint('hello')\n"
        check_qc_3_1_unused_import(code, "python", result, "$.c", 0)
        assert "QC-3.1" in _rule_ids(result)

    def test_used_import_ok(self):
        result = _result()
        code = "import os\n\nprint(os.getcwd())\n"
        check_qc_3_1_unused_import(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc32MissingImport:
    def test_missing_stdlib_import_detected(self):
        result = _result()
        code = "path = os.getcwd()\n"
        check_qc_3_2_missing_import(code, "python", result, "$.c", 0)
        assert "QC-3.2" in _rule_ids(result)

    def test_imported_module_ok(self):
        result = _result()
        code = "import os\n\npath = os.getcwd()\n"
        check_qc_3_2_missing_import(code, "python", result, "$.c", 0)
        assert result.defects == []


class TestQc33HardcodedDemoValue:
    def test_placeholder_password_detected(self):
        result = _result()
        code = 'password = "password"\n'
        check_qc_3_3_hardcoded_demo_value(code, "python", result, "$.c", 0)
        assert "QC-3.3" in _rule_ids(result)

    def test_placeholder_api_key_detected(self):
        result = _result()
        code = 'api_key = "your-api-key"\n'
        check_qc_3_3_hardcoded_demo_value(code, "python", result, "$.c", 0)
        assert "QC-3.3" in _rule_ids(result)

    def test_real_value_ok(self):
        result = _result()
        code = 'password = "correct-horse-battery-staple"\n'
        check_qc_3_3_hardcoded_demo_value(code, "python", result, "$.c", 0)
        assert result.defects == []

    def test_comment_example_not_flagged(self):
        """Documentation examples in comments should not be flagged."""
        result = _result()
        code = '# password = "password"\n'
        check_qc_3_3_hardcoded_demo_value(code, "python", result, "$.c", 0)
        assert result.defects == []
