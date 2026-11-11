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

"""Data models for the extraction-stage IR.

These models are the CLI-side contract of what the ExtractAgent reports via
its ``store_artifacts`` tool. Enumerations are enforced in the tool layer
(with error messages listing allowed values) and re-validated here so the
IR writer and artifact packer never guess or normalize.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

ARTIFACT_TYPES = ("prompt", "skill", "tool")

#: Six completeness labels; the separator in ``original · variable
#: unexpanded`` is U+00B7 (middle dot) and must match byte-exact.
COMPLETENESS_LABELS = (
    "full original",
    "original · variable unexpanded",
    "assembled",
    "incomplete",
    "summary",
    "not inspectable",
)

#: L levels accepted from the extractor. AC-L4 is out of scope for
#: single-agent artifact-set inspection and is rejected.
L_LEVELS = (
    "AC-L1",
    "AC-L2",
    "AC-L3",
    "OR-L1",
    "OR-L2",
    "OR-L3",
    "undetermined",
)

ATTRIBUTION_STATUSES = ("single", "pending")


class FieldEvidence(BaseModel):
    """Per-field provenance for an assembled schema."""

    field: str = Field(min_length=1)
    snippet: str = Field(min_length=1)


class ExtractedArtifact(BaseModel):
    """One object-layer record."""

    type: str
    name: str = Field(min_length=1)
    content: str = ""
    schema_object: dict = Field(default_factory=dict, alias="schema")
    completeness: str
    L: str
    evidence: str = ""
    field_evidence: list[FieldEvidence] = Field(default_factory=list)
    source: str = Field(min_length=1)  # absolute path
    reason: str = ""  # required for completeness="not inspectable"
    #: "agent" for authoritative records, "deterministic" for candidates the
    #: agent never reviewed (recorded with L="undetermined", design §5.5).
    extraction_method: str = "agent"

    model_config = {"populate_by_name": True}

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in ARTIFACT_TYPES:
            raise ValueError(f"type must be one of {ARTIFACT_TYPES}, got {value!r}")
        return value

    @field_validator("completeness")
    @classmethod
    def _check_completeness(cls, value: str) -> str:
        if value not in COMPLETENESS_LABELS:
            raise ValueError(f"completeness must be one of {COMPLETENESS_LABELS}, got {value!r}")
        return value

    @field_validator("L")
    @classmethod
    def _check_L(cls, value: str) -> str:
        if value not in L_LEVELS:
            raise ValueError(f"L must be one of {L_LEVELS}, got {value!r}")
        return value

    @model_validator(mode="after")
    def _check_bindings(self) -> ExtractedArtifact:
        if self.completeness == "assembled" and not self.field_evidence:
            raise ValueError("field_evidence is required when completeness='assembled'")
        if self.completeness == "not inspectable" and not self.reason:
            raise ValueError("reason is required when completeness='not inspectable'")
        if self.completeness == "not inspectable" and self.L != "undetermined":
            raise ValueError("a not-inspectable artifact must carry L='undetermined'")
        if (
            self.type == "tool"
            and not self.schema_object
            and self.completeness
            in (
                "full original",
                "original · variable unexpanded",
                "assembled",
            )
        ):
            raise ValueError("schema object is required for inspectable tool artifacts")
        if self.type != "tool" and self.schema_object:
            raise ValueError("schema object is only valid for type='tool'")
        return self


class ExtractedReference(BaseModel):
    """One reference-layer record."""

    name: str = Field(min_length=1)
    referenced_by: str = Field(min_length=1)
    relationship: str = Field(min_length=1)


class Attribution(BaseModel):
    """Set-level attribution statement."""

    status: str
    note: str = ""

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in ATTRIBUTION_STATUSES:
            raise ValueError(
                f"attribution status must be one of {ATTRIBUTION_STATUSES}, " f"got {value!r}"
            )
        return value


class ExtractionMeta(BaseModel):
    """Run statistics attached by the CLI after the agent finishes."""

    loops_used: int = 0
    tokens_used: int = 0
    time_elapsed: float = 0.0
    deterministic_candidates: int = 0
    resends: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Everything the extraction stage produced.

    Chunk completeness is validated by the ``store_artifacts`` tool before
    these models are built; a record here is a complete chunk stream.
    """

    artifacts: list[ExtractedArtifact] = Field(default_factory=list)
    references: list[ExtractedReference] = Field(default_factory=list)
    attribution: Attribution | None = None
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)
