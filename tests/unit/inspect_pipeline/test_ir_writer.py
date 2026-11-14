"""Tests for the two-layer IR writer (design §2 step ③, §6.2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from sanityops_cli.inspect_pipeline import ir_writer
from sanityops_cli.inspect_pipeline.models import (
    Attribution,
    ExtractedArtifact,
    ExtractedReference,
    ExtractionMeta,
    ExtractionResult,
    FieldEvidence,
)


def artifact(**overrides):
    base = {
        "type": "prompt",
        "name": "system",
        "content": "You are a helpful assistant.",
        "completeness": "full original",
        "L": "AC-L1",
        "evidence": "You are … assistant.",
        "source": "/proj/prompts/system.md",
    }
    base.update(overrides)
    return ExtractedArtifact(**base)


def result(**overrides) -> ExtractionResult:
    base = dict(
        artifacts=[artifact()],
        references=[
            ExtractedReference(name="search", referenced_by="system", relationship="invokes_tool")
        ],
        attribution=Attribution(status="single", note="one config"),
        meta=ExtractionMeta(deterministic_candidates=1),
    )
    base.update(overrides)
    return ExtractionResult(**base)


class TestGrouping:
    def test_groups_by_source_sorted(self):
        res = result(
            artifacts=[
                artifact(source="/b.md", name="second"),
                artifact(source="/a.md", name="first"),
                artifact(source="/b.md", name="third"),
            ]
        )
        grouped = ir_writer.group_by_source(res)
        assert list(grouped) == ["/a.md", "/b.md"]
        assert [a.name for a in grouped["/b.md"]] == ["second", "third"]


class TestDocumentIR:
    def test_renders_object_and_reference_layers(self):
        text = ir_writer.render_document_ir(
            "/proj/prompts/system.md", [artifact()], result().references
        )
        assert "# IR — system.md" in text
        assert "### [prompt] system (full original, AC-L1, agent)" in text
        assert "| search | system | invokes_tool |" in text
        assert '"objects"' in text and '"references"' in text

    def test_ir_core_block_is_valid_json(self):
        text = ir_writer.render_document_ir("/s.md", [artifact()], [])
        block = text.split("## ir-core")[1].strip()
        payload = json.loads(re.search(r"```json\n(.*)\n```", block, re.DOTALL).group(1))
        assert payload["objects"][0]["name"] == "system"
        assert payload["objects"][0]["completeness"] == "full original"

    def test_fence_survives_embedded_backticks(self):
        tricky = artifact(content="intro\n```python\nprint('hi')\n```\nend")
        text = ir_writer.render_document_ir("/s.md", [tricky], [])
        # The outer fence must be longer than any inner fence run (3) → 4.
        outer = re.search(r"(`{4,})\n", text).group(1)
        assert len(outer) == 4
        assert "```python" in text

    def test_fence_survives_content_ending_with_backticks(self):
        tricky = artifact(content="code ends with backticks: ```")
        text = ir_writer.render_document_ir("/s.md", [tricky], [])
        outer = re.search(r"(`{4,})\n", text).group(1)
        assert len(outer) == 4
        assert f"{outer}\ncode ends with backticks: ```\n{outer}" in text

    def test_field_evidence_rendered_for_assembled(self):
        assembled = artifact(
            type="tool",
            name="t",
            content="",
            schema={"name": "t", "parameters": {}},
            completeness="assembled",
            field_evidence=[FieldEvidence(field="name", snippet="def t()")],
        )
        text = ir_writer.render_document_ir("/t.py", [assembled], [])
        assert "| `name` | def t() |" in text

    def test_not_inspectable_shows_reason_no_content(self):
        ni = artifact(
            completeness="not inspectable", reason="binary file", content="", L="undetermined"
        )
        text = ir_writer.render_document_ir("/x.bin", [ni], [])
        assert "Not inspectable: binary file" in text
        assert "You are a helpful" not in text


class TestWriteIRFiles:
    def test_writes_one_file_per_source(self, tmp_path: Path):
        res = result(
            artifacts=[
                artifact(source="/proj/prompts/system.md"),
                artifact(source="/proj/skills/review.md", name="review", type="skill"),
            ]
        )
        written = ir_writer.write_ir_files(res, tmp_path / "ir")
        names = {p.name for p in written}
        assert names == {"system.ir.md", "review.ir.md"}
        assert (
            (tmp_path / "ir" / "system.ir.md")
            .read_text(encoding="utf-8")
            .startswith("# IR — system.md")
        )

    def test_unmatched_references_get_own_file(self, tmp_path: Path):
        res = result(
            references=[
                ExtractedReference(
                    name="ghost", referenced_by="nobody", relationship="invokes_tool"
                )
            ]
        )
        written = ir_writer.write_ir_files(res, tmp_path / "ir")
        assert "_unmatched-references.ir.md" in {p.name for p in written}

    def test_writes_into_run_id_subdirectory(self, tmp_path: Path):
        res1 = result(artifacts=[artifact(source="/proj/prompts/a.md", name="a")], references=[])
        res2 = result(artifacts=[artifact(source="/proj/prompts/b.md", name="b")], references=[])

        w1 = ir_writer.write_ir_files(res1, tmp_path / "ir", run_id="20261110-203500")
        w2 = ir_writer.write_ir_files(res2, tmp_path / "ir", run_id="20261110-203505")

        assert [p.relative_to(tmp_path).as_posix() for p in w1] == ["ir/20261110-203500/a.ir.md"]
        assert [p.relative_to(tmp_path).as_posix() for p in w2] == ["ir/20261110-203505/b.ir.md"]

    def test_same_stem_different_parents_do_not_overwrite(self, tmp_path: Path):
        res = result(
            artifacts=[
                artifact(source="/proj/skills/alpha/SKILL.md", name="alpha", type="skill"),
                artifact(source="/proj/skills/beta/SKILL.md", name="beta", type="skill"),
            ],
            references=[],
        )
        written = ir_writer.write_ir_files(res, tmp_path / "ir", run_id="batch-1")
        assert {p.name for p in written} == {"alpha__SKILL.ir.md", "beta__SKILL.ir.md"}

    def test_same_parent_and_stem_disambiguated_by_hash(self, tmp_path: Path):
        res = result(
            artifacts=[
                artifact(source="/v1/skills/SKILL.md", name="s1", type="skill"),
                artifact(source="/v2/skills/SKILL.md", name="s2", type="skill"),
            ],
            references=[],
        )
        written = ir_writer.write_ir_files(res, tmp_path / "ir")
        assert len(written) == 2
        assert len({p.name for p in written}) == 2
        assert all(
            p.name.startswith("skills__SKILL_") and p.name.endswith(".ir.md") for p in written
        )

    def test_source_named_unmatched_references_preserved(self, tmp_path: Path):
        res = result(
            artifacts=[artifact(source="/proj/_unmatched-references.md", name="u")],
            references=[
                ExtractedReference(
                    name="ghost", referenced_by="nobody", relationship="invokes_tool"
                )
            ],
        )
        written = ir_writer.write_ir_files(res, tmp_path / "ir")
        assert len(written) == 2
        assert "_unmatched-references.ir.md" in {p.name for p in written}

    def test_allocate_run_id_avoids_report_and_dir_collisions(self, tmp_path: Path):
        results_dir = tmp_path / "results"
        assert ir_writer.allocate_run_id(results_dir, timestamp="20261110-203500") == (
            "20261110-203500"
        )
        (results_dir / "ir" / "20261110-203500").mkdir(parents=True)
        assert ir_writer.allocate_run_id(results_dir, timestamp="20261110-203500") == (
            "20261110-203500-2"
        )
        (results_dir / "inspect-20261110-203500-2.md").write_text("r", encoding="utf-8")
        assert ir_writer.allocate_run_id(results_dir, timestamp="20261110-203500") == (
            "20261110-203500-3"
        )


class TestInjectionPayload:
    def test_contains_summary_attribution_objects(self):
        payload = ir_writer.render_injection_payload(result())
        assert "# Extraction IR payload" in payload
        assert "attribution: single — one config" in payload
        assert "prompt: 1" in payload
        assert "### [prompt] system" in payload
        assert "deterministic candidates: 1" in payload

    def test_not_inspectable_listed(self):
        ni = artifact(
            completeness="not inspectable",
            reason="unreadable",
            content="",
            L="undetermined",
            name="bin",
        )
        payload = ir_writer.render_injection_payload(result(artifacts=[artifact(), ni]))
        assert "## Not inspectable" in payload
        assert "[prompt] bin — unreadable" in payload

    def test_unmatched_references_section(self):
        res = result(
            references=[
                ExtractedReference(
                    name="ghost", referenced_by="nobody", relationship="invokes_tool"
                )
            ]
        )
        payload = ir_writer.render_injection_payload(res)
        assert "Unmatched references" in payload
        assert "nobody -> ghost" in payload

    def test_no_attribution_reported(self):
        payload = ir_writer.render_injection_payload(result(attribution=None))
        assert "attribution: not reported" in payload
