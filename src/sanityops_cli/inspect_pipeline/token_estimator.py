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

"""CJK-aware token estimation and injection budget derivation (design §6.6).

The framework's chars/4 heuristic underestimates CJK by roughly 3x. Here a
CJK char counts as ~1 token, other characters as chars/4 — conservative in
the right direction (overestimate → refuse to run rather than overflow).
"""

from __future__ import annotations

import unicodedata


def _is_cjk(char: str) -> bool:
    return unicodedata.east_asian_width(char) in ("F", "W")


def estimate_tokens(text: str) -> int:
    """CJK chars ≈ 1 token; everything else ≈ chars/4."""
    if not text:
        return 0
    cjk = sum(1 for char in text if _is_cjk(char))
    other = len(text) - cjk
    return cjk + other // 4


def derive_injection_budget(
    context_window: int,
    system_prompt: str,
    skill_reserve: int,
    output_reserve: int = 8192,
    work_margin: int = 16384,
) -> int:
    """Tokens available for the injected payload (task message).

    skill_reserve: expected lazy skill loads for this run (§6.6 table);
    the caller estimates it from the artifact-type combination.
    """
    return max(
        0,
        context_window
        - estimate_tokens(system_prompt)
        - skill_reserve
        - output_reserve
        - work_margin,
    )


def estimate_skill_reserve(artifact_types: set[str]) -> int:
    """Expected lazy-load reserve per the §6.6 table (approximate, CJK-aware).

    Only the SKILL.md (~42k) plus the domain checklists the artifact
    combination requires. Values measured on the vendored skill (UTF-8
    bytes; CJK-aware estimate is close to byte count for mostly-ASCII text).
    """
    reserve = 42_000  # SKILL.md
    if "prompt" in artifact_types:
        reserve += 16_000  # prompt-checklist
    if "tool" in artifact_types:
        reserve += 11_000  # tool-checklist
    if len(artifact_types & {"prompt", "skill", "tool"}) >= 2:
        reserve += 12_000  # cross-checklist
        reserve += 5_000  # _meta guidance
    if "skill" in artifact_types:
        reserve += 16_000  # skill-checklist
    return reserve
