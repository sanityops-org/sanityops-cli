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

"""Compaction trigger fix for artifact-heavy agent runs (design §5.4).

The framework's ``AgentContext.estimate_tokens()`` counts text, thinking,
and tool-result content as chars/4 — it cannot see ``ToolUseBlock.tool_input``.
The ExtractAgent's payloads live exactly there (store_artifacts arguments),
so large artifact deliveries are invisible to the compaction trigger and the
context grows unbounded until the provider rejects the request with
``ContextWindowExceededError`` (recoverable=False, kills the whole run).

``ArtifactAwareContext`` extends the estimate with the serialized size of
every tool-use input, cached per ``tool_call_id`` (tool inputs are immutable
once emitted, so each block is serialized exactly once).
"""

from __future__ import annotations

import json

from sanityops_agent.core.context import AgentContext, CompactConfig
from sanityops_agent.core.message import ToolUseBlock


class ArtifactAwareContext(AgentContext):
    """AgentContext whose token estimate includes tool-call input payloads."""

    def __init__(self, compact_config: CompactConfig | None = None) -> None:
        super().__init__(compact_config=compact_config or CompactConfig())
        self._tool_input_sizes: dict[str, int] = {}

    def estimate_tokens(self) -> int:
        base = super().estimate_tokens()
        extra = 0
        for msg in self.messages:
            for block in msg.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                size = self._tool_input_sizes.get(block.tool_call_id)
                if size is None:
                    size = len(json.dumps(block.tool_input, ensure_ascii=False, default=str)) // 4
                    self._tool_input_sizes[block.tool_call_id] = size
                extra += size
        return base + extra
