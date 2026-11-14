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

"""Shared agent termination diagnostics."""

from __future__ import annotations

from sanityops_agent.core.agent import TerminationReason


def _termination_message(
    stage: str,
    reason: TerminationReason,
    detail: list[str],
) -> str:
    """Build an actionable message for an abnormal agent termination."""
    suffix = f"; last error: {detail[-1]}" if detail else ""
    if reason == TerminationReason.HOOK_BLOCKED:
        return (
            f"{stage} agent stopped: the model kept answering without calling any "
            f"tool for several consecutive turns, so the run would never produce "
            f"auditable output (hook_blocked)"
        )
    if reason == TerminationReason.TIMEOUT:
        return (
            f"{stage} agent timed out: the run exceeded the --timeout budget "
            f"(timeout){suffix}"
        )
    if reason == TerminationReason.MAX_LOOPS:
        return (
            f"{stage} agent hit the loop limit without ending its turn "
            f"(max_loops){suffix}"
        )
    if reason == TerminationReason.TOKEN_BUDGET:
        return (
            f"{stage} agent exceeded the token budget "
            f"(token_budget){suffix}"
        )
    return f"{stage} agent terminated abnormally: {reason.value}{suffix}"
