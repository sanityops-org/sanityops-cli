"""Code Contract inspection rules (17-item checklist v2)."""

from .qc0_baseline import (
    CodeBlock,
    check_qc_0_1_syntax_parsability,
    check_qc_0_2_language_declaration,
    check_qc_0_3_structural_completeness,
    extract_code_blocks,
)
from .qc0_fence import (
    check_qc_0_4_fence_integrity,
    check_qc_0_5_language_content_mismatch,
)
from .qc1_imports import (
    check_qc_1_2_invalid_import,
    check_qc_1_3_deprecated_api,
)
from .qc1_syntax import (
    check_qc_1_1_undefined_name,
    check_qc_1_4_type_mismatch,
)
from .qc2_resource import (
    check_qc_2_1_unclosed_file_handle,
    check_qc_2_2_unreleased_network,
    check_qc_2_3_missing_exception_handling,
)
from .qc3_pattern import (
    check_qc_3_1_unused_import,
    check_qc_3_2_missing_import,
    check_qc_3_3_hardcoded_demo_value,
)
from .qc4_drift import (
    check_qc_4_1_snippet_artifact_mismatch,
    check_qc_4_2_snippet_body_drift,
    extract_snippet_param_names,
)

__all__ = [
    # QC-0 Baseline
    "CodeBlock",
    "check_qc_0_1_syntax_parsability",
    "check_qc_0_2_language_declaration",
    "check_qc_0_3_structural_completeness",
    "check_qc_0_4_fence_integrity",
    "check_qc_0_5_language_content_mismatch",
    "extract_code_blocks",
    # QC-1 Syntax
    "check_qc_1_1_undefined_name",
    "check_qc_1_2_invalid_import",
    "check_qc_1_3_deprecated_api",
    "check_qc_1_4_type_mismatch",
    # QC-2 Resource
    "check_qc_2_1_unclosed_file_handle",
    "check_qc_2_2_unreleased_network",
    "check_qc_2_3_missing_exception_handling",
    # QC-3 Pattern
    "check_qc_3_1_unused_import",
    "check_qc_3_2_missing_import",
    "check_qc_3_3_hardcoded_demo_value",
    # QC-4 Drift
    "check_qc_4_1_snippet_artifact_mismatch",
    "check_qc_4_2_snippet_body_drift",
    "extract_snippet_param_names",
]
