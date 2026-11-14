"""Tests for extraction IR models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sanityops_cli.inspect_pipeline.models import (
    Attribution,
    ExtractedArtifact,
    ExtractedReference,
)


def artifact(**overrides):
    base = {
        "type": "prompt",
        "name": "system",
        "content": "You are.",
        "completeness": "full original",
        "L": "AC-L2",
        "source": "/p/system.md",
    }
    base.update(overrides)
    return base


class TestExtractedArtifact:
    def test_valid_artifact(self):
        record = ExtractedArtifact(**artifact())
        assert record.name == "system"
        assert record.field_evidence == []

    def test_alias_schema_object(self):
        record = ExtractedArtifact(**artifact(type="tool", schema={"name": "t"}, content=""))
        assert record.schema_object == {"name": "t"}

    @pytest.mark.parametrize(
        "overrides, fragment",
        [
            ({"type": "function"}, "type must be one of"),
            ({"completeness": "full  original"}, "completeness must be one of"),
            ({"L": "AC-L4"}, "L must be one of"),
            ({"completeness": "assembled"}, "field_evidence is required"),
            ({"completeness": "not inspectable"}, "reason is required"),
        ],
    )
    def test_rejections(self, overrides, fragment):
        with pytest.raises(ValidationError, match=fragment):
            ExtractedArtifact(**artifact(**overrides))

    def test_not_inspectable_requires_undetermined_L(self):
        with pytest.raises(ValidationError, match="undetermined"):
            ExtractedArtifact(
                **artifact(completeness="not inspectable", reason="binary", L="AC-L1")
            )

    def test_tool_requires_schema_when_inspectable(self):
        with pytest.raises(ValidationError, match="schema object is required"):
            ExtractedArtifact(**artifact(type="tool", content="{}", completeness="full original"))

    def test_schema_rejected_on_non_tool(self):
        with pytest.raises(ValidationError, match="only valid for type='tool'"):
            ExtractedArtifact(**artifact(schema={"x": 1}))


class TestAttributionAndReference:
    def test_attribution_enum(self):
        assert Attribution(status="single").status == "single"
        with pytest.raises(ValidationError, match="status must be one of"):
            Attribution(status="collective")

    def test_reference_min_lengths(self):
        ExtractedReference(name="t", referenced_by="p", relationship="invokes_tool")
        with pytest.raises(ValidationError):
            ExtractedReference(name="", referenced_by="p", relationship="invokes_tool")
