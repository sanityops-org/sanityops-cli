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

"""Code Contract inspection rules."""

from .qc0_baseline import (
    check_qc_0_1_syntax_parsability,
    check_qc_0_2_language_declaration,
    check_qc_0_3_structural_completeness,
    extract_code_blocks,
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

__all__ = [
    # QC-0 Baseline
    "check_qc_0_1_syntax_parsability",
    "check_qc_0_2_language_declaration",
    "check_qc_0_3_structural_completeness",
    "extract_code_blocks",
    # QC-1 Syntax
    "check_qc_1_1_undefined_name",
    "check_qc_1_4_type_mismatch",
    # QC-2 Resource
    "check_qc_2_1_unclosed_file_handle",
    "check_qc_2_2_unreleased_network",
    "check_qc_2_3_missing_exception_handling",
    # QC-3 Pattern
    "check_qc_3_1_unused_import",
    "check_qc_3_2_missing_import",
    "check_qc_3_3_hardcoded_demo_value",
]
