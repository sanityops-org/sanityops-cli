"""Tests for the store_artifacts chunked-delivery protocol (design §5.3)."""

from __future__ import annotations

import asyncio
import json

import pytest

from sanityops_cli.agents.extract_agent.tools.store_artifacts_tool import (
    MAX_CHUNK_CHARS,
    StoreArtifactsTool,
)


def run(tool: StoreArtifactsTool, **kwargs):
    return asyncio.run(tool.run(**kwargs))


def artifact(**overrides):
    base = {
        "type": "prompt",
        "name": "system",
        "content": "You are a helpful assistant.",
        "completeness": "full original",
        "L": "AC-L2",
        "evidence": "You are a helpful … assistant.",
        "source": "/proj/prompts/system.md",
    }
    base.update(overrides)
    return base


class TestSingleChunk:
    def test_single_chunk_ack_and_finalize(self):
        tool = StoreArtifactsTool()
        result = run(
            tool, operation="add_artifact", artifact=artifact(total_chunks=1, final=True, seq=0)
        )
        assert result.success
        assert "artifact complete" in result.content
        artifacts, incomplete = tool.finalize()
        assert incomplete == []
        assert len(artifacts) == 1
        record = artifacts[0]
        assert record.type == "prompt"
        assert record.name == "system"
        assert record.content == "You are a helpful assistant."
        assert record.completeness == "full original"
        assert record.L == "AC-L2"
        assert record.source == "/proj/prompts/system.md"

    def test_final_chunk_requires_metadata(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "x",
                "content": "hi",
                "total_chunks": 1,
                "seq": 0,
                "final": True,
            },
        )
        assert not result.success
        assert "completeness" in result.error
        # Nothing consumed: retry with complete metadata succeeds.
        result2 = run(tool, operation="add_artifact", artifact=artifact(total_chunks=1, final=True))
        assert result2.success

    def test_single_chunk_default_seq_is_zero(self):
        tool = StoreArtifactsTool()
        result = run(tool, operation="add_artifact", artifact=artifact(total_chunks=1, final=True))
        assert result.success


class TestChunkSequence:
    def test_multi_chunk_stream(self):
        tool = StoreArtifactsTool()
        r0 = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "part-one ",
                "total_chunks": 2,
                "seq": 0,
            },
        )
        assert r0.success
        assert json.loads(r0.content)["next_expected"] == 1
        r1 = run(
            tool,
            operation="add_artifact",
            artifact=artifact(name="p", content="part-two", total_chunks=2, seq=1, final=True),
        )
        assert r1.success
        artifacts, incomplete = tool.finalize()
        assert incomplete == []
        assert artifacts[0].content == "part-one \npart-two"

    def test_out_of_order_seq_rejected_without_consuming(self):
        tool = StoreArtifactsTool()
        run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "a", "total_chunks": 3, "seq": 0},
        )
        bad = run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "c", "total_chunks": 3, "seq": 2},
        )
        assert not bad.success
        assert "expected chunk 1" in bad.error
        good = run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "b", "total_chunks": 3, "seq": 1},
        )
        assert good.success

    def test_first_chunk_must_declare_total(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "a", "seq": 0},
        )
        assert not result.success
        assert "total_chunks" in result.error

    def test_final_on_wrong_seq_rejected(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "a",
                "total_chunks": 2,
                "seq": 0,
                "final": True,
            },
        )
        assert not result.success
        assert "final must be seq=1" in result.error

    def test_missing_final_on_last_chunk_rejected(self):
        tool = StoreArtifactsTool()
        run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "a", "total_chunks": 2, "seq": 0},
        )
        result = run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "b", "total_chunks": 2, "seq": 1},
        )
        assert not result.success
        assert "set final=true" in result.error

    def test_chunk_size_cap(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "x" * (MAX_CHUNK_CHARS + 1),
                "total_chunks": 2,
                "seq": 0,
            },
        )
        assert not result.success
        assert "split into chunks" in result.error


class TestResendSemantics:
    def test_restart_from_seq_zero_wins(self):
        tool = StoreArtifactsTool()
        run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "stale-a",
                "total_chunks": 2,
                "seq": 0,
            },
        )
        run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "stale-b",
                "total_chunks": 2,
                "seq": 1,
                "final": True,
                "completeness": "full original",
                "L": "AC-L1",
                "source": "/s",
            },
        )
        # Agent discovers a mistake, restarts the whole stream.
        run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "good-a ",
                "total_chunks": 2,
                "seq": 0,
            },
        )
        run(
            tool,
            operation="add_artifact",
            artifact=artifact(name="p", content="good-b", total_chunks=2, seq=1, final=True),
        )
        artifacts, incomplete = tool.finalize()
        assert incomplete == []
        assert artifacts[0].content == "good-a \ngood-b"
        assert tool.resend_log == ["prompt/p"]

    def test_failed_restart_preserves_old_stream(self):
        tool = StoreArtifactsTool()
        run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "a", "total_chunks": 2, "seq": 0},
        )
        # Malformed restart (no total_chunks): old stream must survive.
        bad = run(
            tool,
            operation="add_artifact",
            artifact={"type": "prompt", "name": "p", "content": "restart", "seq": 0},
        )
        assert not bad.success
        good = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "prompt",
                "name": "p",
                "content": "b",
                "total_chunks": 2,
                "seq": 1,
                "final": True,
                "completeness": "summary",
                "L": "AC-L1",
                "source": "/s",
            },
        )
        assert good.success
        artifacts, incomplete = tool.finalize()
        assert incomplete == []
        assert artifacts[0].content == "a\nb"
        assert tool.resend_log == []


class TestValidation:
    @pytest.mark.parametrize(
        "overrides, fragment",
        [
            ({"completeness": "FULL ORIGINAL"}, "completeness must be one of"),
            ({"L": "AC-L4"}, "L must be one of"),
            ({"L": "L2"}, "L must be one of"),
            ({"completeness": "assembled"}, "field_evidence is required"),
            ({"completeness": "not inspectable"}, "reason is required"),
            ({"type": "function"}, "type must be one of"),
        ],
    )
    def test_rejections(self, overrides, fragment):
        tool = StoreArtifactsTool()
        payload = artifact(total_chunks=1, final=True, **overrides)
        if overrides.get("completeness") == "not inspectable":
            payload.pop("reason", None)
        result = run(tool, operation="add_artifact", artifact=payload)
        assert not result.success
        assert fragment in result.error

    def test_exact_middle_dot_label_accepted(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact=artifact(
                completeness="original · variable unexpanded", total_chunks=1, final=True
            ),
        )
        assert result.success

    def test_assembled_requires_field_evidence_and_tool_schema(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "tool",
                "name": "t",
                "schema": {"name": "t", "parameters": {}},
                "completeness": "assembled",
                "L": "OR-L1",
                "field_evidence": [{"field": "name", "snippet": "def t()"}],
                "source": "/proj/t.py",
                "total_chunks": 1,
                "final": True,
            },
        )
        assert result.success

    def test_schema_must_be_object(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "tool",
                "name": "t",
                "schema": "not-an-object",
                "total_chunks": 1,
                "seq": 0,
            },
        )
        assert not result.success
        assert "JSON object" in result.error


class TestReferencesAndAttribution:
    def test_reference_roundtrip(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="add_reference",
            reference={"name": "search", "referenced_by": "system", "relationship": "invokes_tool"},
        )
        assert result.success
        assert len(tool.references) == 1
        assert tool.references[0].name == "search"

    def test_reference_requires_all_fields(self):
        tool = StoreArtifactsTool()
        result = run(tool, operation="add_reference", reference={"name": "search"})
        assert not result.success
        assert "referenced_by" in result.error

    def test_attribution_roundtrip(self):
        tool = StoreArtifactsTool()
        result = run(
            tool,
            operation="set_attribution",
            attribution={"status": "single", "note": "one config"},
        )
        assert result.success
        assert tool.attribution.status == "single"

    def test_attribution_status_enum(self):
        tool = StoreArtifactsTool()
        result = run(tool, operation="set_attribution", attribution={"status": "collective"})
        assert not result.success
        assert "must be one of" in result.error


class TestListResync:
    def test_list_reports_state(self):
        tool = StoreArtifactsTool()
        run(tool, operation="add_artifact", artifact=artifact(total_chunks=1, final=True))
        run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "tool",
                "name": "t",
                "schema": {"name": "t"},
                "total_chunks": 2,
                "seq": 0,
            },
        )
        run(
            tool,
            operation="add_reference",
            reference={"name": "search", "referenced_by": "system", "relationship": "invokes_tool"},
        )
        run(tool, operation="set_attribution", attribution={"status": "single"})
        result = run(tool, operation="list")
        payload = json.loads(result.content)
        by_name = {a["name"]: a for a in payload["artifacts"]}
        assert by_name["system"]["final"] is True
        assert by_name["t"]["chunks"] == "1/2"
        assert by_name["t"]["final"] is False
        assert payload["references"] == 1
        assert payload["attribution"] == "single"

    def test_finalize_excludes_incomplete(self):
        tool = StoreArtifactsTool()
        run(tool, operation="add_artifact", artifact=artifact(total_chunks=1, final=True))
        run(
            tool,
            operation="add_artifact",
            artifact={
                "type": "skill",
                "name": "s",
                "content": "partial",
                "total_chunks": 3,
                "seq": 0,
            },
        )
        artifacts, incomplete = tool.finalize()
        assert [a.name for a in artifacts] == ["system"]
        assert incomplete == ["skill/s"]

    def test_instance_state_not_shared(self):
        a, b = StoreArtifactsTool(), StoreArtifactsTool()
        run(a, operation="add_artifact", artifact=artifact(total_chunks=1, final=True))
        assert len(b.finalize()[0]) == 0
