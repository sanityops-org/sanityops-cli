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

"""Convert FindingsResult into defect-check SDK input and invoke the SDK."""

from __future__ import annotations

import defect_check

from sanityops_cli.agents.scanner_agent.models.finding import (
    Finding,
    FindingsResult,
    FindingType,
)


class DefectChecker:
    """Checks extracted artifacts for defects using the defect-check SDK."""

    def __init__(self, llm_config: dict[str, str]):
        """Initialize with the resolved LLM config.

        Args:
            llm_config: dict with keys llm_provider, llm_api_key,
                llm_model_id, llm_base_url.
        """
        self.llm_config = llm_config

    async def check(
        self,
        findings: FindingsResult,
        check_level: str = "L2",
    ) -> dict:
        """Run defect check and return the raw SDK response dict."""
        tools = self._convert_tools(findings.tools)
        prompts = self._convert_prompts(findings.prompts)
        skills = self._convert_skills(findings.skills)

        return await defect_check.check(
            tools=tools,
            prompts=prompts,
            skills=skills,
            check_level=check_level,
            llm_provider=self.llm_config.get("llm_provider"),
            llm_api_key=self.llm_config.get("llm_api_key"),
            llm_model_id=self.llm_config.get("llm_model_id"),
            llm_base_url=self.llm_config.get("llm_base_url"),
        )

    def _convert_tools(self, tools: list[Finding]) -> list[dict]:
        result: list[dict] = []
        for finding in tools:
            content = finding.content
            if content is None or finding.type != FindingType.TOOL:
                continue
            result.append({
                "name": content.name,
                "description": content.description,
                "parameters": content.parameters,
            })
        return result

    def _convert_prompts(self, prompts: list[Finding]) -> list[dict]:
        result: list[dict] = []
        for finding in prompts:
            content = finding.content
            if content is None or finding.type != FindingType.PROMPT:
                continue
            result.append({"content": content.content})
        return result

    def _convert_skills(self, skills: list[Finding]) -> list[dict]:
        result: list[dict] = []
        for finding in skills:
            content = finding.content
            if content is None or finding.type != FindingType.SKILL:
                continue
            result.append({
                "id": finding.relative,
                "name": content.name,
                "content": content.to_markdown(),
            })
        return result
