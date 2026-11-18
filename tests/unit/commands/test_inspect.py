"""Unit tests for the skill-based inspect command orchestration (design §3/§9)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from sanityops_cli.agents.inspect_agent.agent import (
    InspectionFailedError,
    InspectionOutcome,
)
from sanityops_cli.constants.exit_codes import EXIT_DEFECTS_FOUND, EXIT_FAILURE
from sanityops_cli.inspect_pipeline.models import (
    Attribution,
    ExtractedArtifact,
    ExtractionMeta,
    ExtractionResult,
)
from sanityops_cli.main import app

runner = CliRunner()


def _tail_json(status: str = "completed", inspect_p0: int = 0) -> str:
    findings = []
    if inspect_p0:
        findings.append(
            {
                "stage": "A",
                "module": "QD-P",
                "artifact": "system",
                "id": "QD-P-1.1",
                "severity": "P0",
                "description": "contradiction",
            }
        )
    counts = {
        "inspect": {"p0": inspect_p0, "p1": 0, "p2": 0},
        "risk_explicit": {"p0": 0, "p1": 0, "p2": 0},
    }
    return (
        "<!-- inspect-summary -->\n"
        + json.dumps(
            {
                "status": status,
                "stages": {s: "executed" for s in "ABCDEFG"},
                "counts": counts,
                "findings": findings,
            }
        )
        + "\n<!-- /inspect-summary -->"
    )


def _extraction_result(tmp_path: Path) -> ExtractionResult:
    artifact_file = tmp_path / "system-prompt.md"
    artifact_file.write_text("# System prompt\nYou are a helpful agent.\n")
    from sanityops_cli.inspect_pipeline.models import ExtractedArtifact

    return ExtractionResult(
        artifacts=[
            ExtractedArtifact(
                type="prompt",
                name="system",
                content=artifact_file.read_text(encoding="utf-8"),
                completeness="full original",
                L="undetermined",
                source=str(artifact_file),
            )
        ],
        meta=ExtractionMeta(loops_used=3, tokens_used=1200, time_elapsed=4.2),
    )


def _outcome(
    tail: str | None = None,
    *,
    section_parts: dict | None = None,
    missing_stages: list[str] | None = None,
) -> InspectionOutcome:
    return InspectionOutcome(
        report_markdown="# Report\n",
        tail_text=tail if tail is not None else _tail_json(),
        section_parts=section_parts if section_parts is not None else {"A": ["## Stage A\nok"]},
        missing_stages=missing_stages or [],
        termination_reason="END_TURN",
        loops_used=5,
        tokens_used=9000,
        time_elapsed=12.0,
    )


class Harness:
    """Patches LLM config, skills runtime, and both agents; records calls."""

    def __init__(self, monkeypatch, tmp_path: Path):
        self.captured = {
            "extract": None,
            "inspect": None,
            "uploads": 0,
            "llm_resolved": 0,
        }
        self.extraction_result = _extraction_result(tmp_path)
        self.outcome = _outcome()
        self.extract_error: Exception | None = None
        self.inspect_error: Exception | None = None

        def fake_resolve(_config):
            self.captured["llm_resolved"] += 1
            return {
                "llm_provider": "anthropic",
                "llm_api_key": "test-api-key",
                "llm_model_id": "claude-sonnet",
                "llm_base_url": "",
            }

        def fake_upload(_project_id, _result, **_kwargs):
            self.captured["uploads"] += 1

        skills_dir = tmp_path / "skills"
        (skills_dir / "sanityops-inspect-lite").mkdir(parents=True, exist_ok=True)
        (skills_dir / "sanityops-inspect-lite" / "SKILL.md").write_text(
            "---\nname: sanityops-inspect-lite\nversion: 1.0.0\ndescription: x\n---\n# S\n",
            encoding="utf-8",
        )

        harness = self

        class FakeExtractAgent:
            def __init__(self, provider, **kwargs):
                self.kwargs = kwargs
                harness.captured["extract"] = kwargs

            def extract_sync(self, prompts, tools, skills):
                harness.captured["extract_manifest"] = {
                    "prompts": prompts,
                    "tools": tools,
                    "skills": skills,
                }
                if harness.extract_error:
                    raise harness.extract_error
                return harness.extraction_result

        class FakeInspectAgent:
            def __init__(self, provider, **kwargs):
                self.kwargs = kwargs
                harness.captured["inspect"] = kwargs

            def inspect_sync(self):
                if harness.inspect_error:
                    raise harness.inspect_error
                return harness.outcome

        monkeypatch.setattr("sanityops_cli.commands.inspect.resolve_llm_config", fake_resolve)
        monkeypatch.setattr("sanityops_cli.commands.inspect._auto_upload", fake_upload)
        monkeypatch.setattr(
            "sanityops_cli.inspect_pipeline.skill_runtime.materialize_skills",
            lambda source=None, cache_root=None: skills_dir,
        )
        monkeypatch.setattr(
            "sanityops_cli.inspect_pipeline.skill_runtime.validate_vendor",
            lambda skills_dir: [],
        )
        monkeypatch.setattr(
            "sanityops_cli.agents.extract_agent.agent.ExtractAgent", FakeExtractAgent
        )
        monkeypatch.setattr(
            "sanityops_cli.agents.inspect_agent.agent.InspectAgent", FakeInspectAgent
        )

    def run(self, tmp_path: Path, *extra_args: str, config_text: str | None = None):
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n", encoding="utf-8")
        cfg = tmp_path / "inspect_config.yaml"
        cfg.write_text(
            config_text
            or (
                "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
                f"skills:\n  - file: {skill_file}\n"
            ),
            encoding="utf-8",
        )
        return runner.invoke(app, ["inspect", "--config", str(cfg), *extra_args])


def test_inspect_happy_path(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(tmp_path)
    assert result.exit_code == 0, result.output
    assert harness.captured["extract"] is not None
    assert harness.captured["inspect"] is not None
    assert harness.captured["uploads"] == 1
    # report persisted next to the config
    reports = list((tmp_path / "results").glob("inspect-*.md"))
    assert reports, "no inspect report written"
    run_id = reports[0].stem.removeprefix("inspect-")
    ir_batch_dir = tmp_path / "results" / "ir" / run_id
    assert ir_batch_dir.is_dir()
    assert list(ir_batch_dir.glob("*.ir.md"))


def test_inspect_isolates_ir_by_run_batch(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)

    file_a = tmp_path / "a.md"
    file_b = tmp_path / "b.md"
    file_a.write_text("---\nname: a\ndescription: d\n---\n# A\n", encoding="utf-8")
    file_b.write_text("---\nname: b\ndescription: d\n---\n# B\n", encoding="utf-8")

    harness.extraction_result = ExtractionResult(
        artifacts=[
            ExtractedArtifact(
                type="skill",
                name="a",
                content="# A",
                completeness="full original",
                L="AC-L1",
                source=str(file_a),
            )
        ],
        attribution=Attribution(status="single"),
    )
    r1 = harness.run(
        tmp_path,
        config_text=f"project:\n  id: 00000000-0000-0000-0000-000000000000\nskills:\n  - file: {file_a}\n",
    )
    assert r1.exit_code == 0, r1.output

    harness.extraction_result = ExtractionResult(
        artifacts=[
            ExtractedArtifact(
                type="skill",
                name="b",
                content="# B",
                completeness="full original",
                L="AC-L1",
                source=str(file_b),
            )
        ],
        attribution=Attribution(status="single"),
    )
    r2 = harness.run(
        tmp_path,
        config_text=f"project:\n  id: 00000000-0000-0000-0000-000000000000\nskills:\n  - file: {file_b}\n",
    )
    assert r2.exit_code == 0, r2.output

    ir_root = tmp_path / "results" / "ir"
    batch_dirs = sorted(p for p in ir_root.iterdir() if p.is_dir())
    assert len(batch_dirs) == 2
    assert {p.name for p in batch_dirs[0].glob("*.ir.md")} == {"a.ir.md"}
    assert {p.name for p in batch_dirs[1].glob("*.ir.md")} == {"b.ir.md"}
    reports = list((tmp_path / "results").glob("inspect-*.md"))
    assert {p.stem.removeprefix("inspect-") for p in reports} == {d.name for d in batch_dirs}


def test_inspect_report_language_plumbed(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            "report_language: zh\n"
            f"skills:\n  - file: {tmp_path / 'skill.md'}\n"
        ),
    )
    assert result.exit_code == 0, result.output
    assert harness.captured["extract"]["report_language"] == "zh"
    assert harness.captured["inspect"]["report_language"] == "zh"


def test_inspect_timeout_passed_to_both_agents(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(tmp_path, "--timeout", "60")
    assert result.exit_code == 0, result.output
    assert harness.captured["extract"]["timeout"] == 60
    assert harness.captured["inspect"]["timeout"] == 60


def test_inspect_skip_extract(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(tmp_path, "--skip-extract")
    assert result.exit_code == 0, result.output
    assert harness.captured["extract"] is None  # ExtractAgent never constructed
    assert harness.captured["uploads"] == 0  # skip-extract never uploads
    assert harness.captured["inspect"] is not None
    # injection payload built from verbatim injection
    assert "full original" in harness.captured["inspect"]["injection_payload"]


def test_inspect_strict_qc_gate_fail_exits_before_llm(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)

    def explode(_config):
        raise AssertionError("LLM config must not be resolved after a QC gate failure")

    import sanityops_cli.commands.inspect as inspect_module

    monkeypatch.setattr(inspect_module, "resolve_llm_config", explode)

    bad_prompt = tmp_path / "bad.md"
    bad_prompt.write_text("```python\ndef broken(:\n```\n", encoding="utf-8")
    result = harness.run(
        tmp_path,
        "--strict",
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            f"prompts:\n  - file: {bad_prompt}\n"
        ),
    )
    assert result.exit_code == EXIT_DEFECTS_FOUND
    assert harness.captured["llm_resolved"] == 0
    assert harness.captured["inspect"] is None


def test_inspect_strict_p0_exits_1(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    harness.outcome = _outcome(_tail_json(inspect_p0=1))
    result = harness.run(tmp_path, "--strict")
    assert result.exit_code == EXIT_DEFECTS_FOUND


def test_inspect_p0_without_strict_exits_0(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    harness.outcome = _outcome(_tail_json(inspect_p0=1))
    result = harness.run(tmp_path)
    assert result.exit_code == 0, result.output


def test_inspect_strict_missing_stage_exits_1(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    harness.outcome = _outcome(missing_stages=["B"])
    result = harness.run(tmp_path, "--strict")
    assert result.exit_code == EXIT_DEFECTS_FOUND
    assert "Stage completeness gate" in result.output


def test_inspect_extraction_failure_exits_2(monkeypatch, tmp_path):
    from sanityops_cli.agents.extract_agent.agent import ExtractionFailedError

    harness = Harness(monkeypatch, tmp_path)
    harness.extract_error = ExtractionFailedError("provider exploded")
    result = harness.run(tmp_path)
    assert result.exit_code == EXIT_FAILURE
    assert harness.captured["inspect"] is None


def test_inspect_empty_manifest_exits_2(monkeypatch, tmp_path):
    """The config loader rejects an empty manifest before any agent runs."""
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        config_text="project:\n  id: 00000000-0000-0000-0000-000000000000\n",
    )
    assert result.exit_code == EXIT_FAILURE
    assert "Configuration validation failed" in result.output
    assert harness.captured["inspect"] is None
    assert harness.captured["extract"] is None


def test_inspect_empty_extraction_exits_2(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    harness.extraction_result = ExtractionResult(artifacts=[])
    result = harness.run(tmp_path)
    assert result.exit_code == EXIT_FAILURE
    assert "Empty Extraction" in result.output


def test_inspect_non_end_turn_saves_partial_report_and_exits_2(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    partial = _outcome(section_parts={"A": ["## Stage A\npartial"]}, missing_stages=["B"])
    harness.inspect_error = InspectionFailedError("terminated", partial=partial)
    result = harness.run(tmp_path)
    assert result.exit_code == EXIT_FAILURE
    assert "Partial report saved" in result.output
    assert list((tmp_path / "results").glob("inspect-*.md"))


def test_inspect_unparseable_tail_exits_2(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    harness.outcome = _outcome(tail="no tail block here", section_parts={})
    result = harness.run(tmp_path)
    assert result.exit_code == EXIT_FAILURE
    assert "could not be parsed" in result.output


def test_inspect_injection_budget_exceeded_exits_2(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            "context_window: 500\n"
            f"skills:\n  - file: {tmp_path / 'skill.md'}\n"
        ),
    )
    assert result.exit_code == EXIT_FAILURE
    assert "Injection Budget Exceeded" in result.output
    assert harness.captured["inspect"] is None


def test_inspect_attribution_auto_non_tty_degrades_to_collection(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(tmp_path)
    assert result.exit_code == 0, result.output
    inspect_kwargs = harness.captured["inspect"]
    assert inspect_kwargs["attribution"] == "pending"
    assert "non-interactive" in inspect_kwargs["attribution_note"]


def test_inspect_attribution_single_config(monkeypatch, tmp_path):
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            "attribution: single\n"
            f"skills:\n  - file: {tmp_path / 'skill.md'}\n"
        ),
    )
    assert result.exit_code == 0, result.output
    inspect_kwargs = harness.captured["inspect"]
    assert inspect_kwargs["attribution"] == "single"


def test_inspect_qc_program_findings_merged_into_summary(monkeypatch, tmp_path):
    """QC-3.3 (program channel) surfaces in the terminal QC panel via merge."""
    demo_prompt = tmp_path / "demo.md"
    demo_prompt.write_text("```python\nimport os\npassword = '123456'\n```\n", encoding="utf-8")
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        "--verbose",
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            f"prompts:\n  - file: {demo_prompt}\n"
        ),
    )
    assert result.exit_code == 0, result.output
    assert "QC-3.3" in result.output


def test_inspect_qc_candidates_injected_into_inspect_agent(monkeypatch, tmp_path):
    """A hybrid pre-screen hit (QC-0.5) reaches the InspectAgent as a candidate."""
    mismatch_prompt = tmp_path / "mismatch.md"
    mismatch_prompt.write_text(
        "```python\necho 'installing'\napt-get install -y curl\n```\n", encoding="utf-8"
    )
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(
        tmp_path,
        config_text=(
            "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
            f"prompts:\n  - file: {mismatch_prompt}\n"
        ),
    )
    assert result.exit_code == 0, result.output
    candidates = harness.captured["inspect"]["qc_candidates"]
    assert any(c["id"] == "QC-0.5" for c in candidates)
    assert all("model_prompt" in c for c in candidates)


def test_extract_without_agent_skill_dir_handling(tmp_path: Path):
    """Ensure _extract_without_agent handles skill dirs gracefully (with or without SKILL.md)."""
    from sanityops_cli.commands.inspect import _extract_without_agent

    valid_skill_dir = tmp_path / "valid_skill"
    valid_skill_dir.mkdir()
    (valid_skill_dir / "SKILL.md").write_text("# Valid Skill\nInstructions", encoding="utf-8")

    empty_skill_dir = tmp_path / "empty_skill"
    empty_skill_dir.mkdir()

    single_skill_file = tmp_path / "standalone.md"
    single_skill_file.write_text("# Standalone", encoding="utf-8")

    result = _extract_without_agent(
        prompt_files=[],
        tool_files=[],
        skill_files=[str(valid_skill_dir), str(empty_skill_dir), str(single_skill_file)],
    )

    artifacts_by_name = {a.name: a for a in result.artifacts}
    assert artifacts_by_name["valid_skill"].content == "# Valid Skill\nInstructions"
    assert artifacts_by_name["empty_skill"].content == ""
    assert artifacts_by_name["standalone"].content == "# Standalone"


def test_auto_upload_uses_config_path_and_preserves_project_name(monkeypatch, tmp_path: Path):
    """_auto_upload respects cross-directory config_path and configured project.name."""
    import yaml

    from sanityops_cli.commands.inspect import _auto_upload
    from sanityops_cli.inspect_pipeline.models import ExtractedArtifact, ExtractionResult

    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    proj_dir = tmp_path / "my-target-proj"
    cfg_path = proj_dir / ".sanityops" / "inspect_config.yaml"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text(
        'project:\n  id: "00000000-0000-0000-0000-000000000000"\n  name: custom-agent\n',
        encoding="utf-8",
    )

    global_cfg = tmp_path / "global_config"
    global_cfg.write_text(
        "server:\n  base_url: http://localhost:3000/\n  api_key: dl-test-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sanityops_cli.utils.config_resolver.get_global_config_path",
        lambda: global_cfg,
    )

    calls: dict[str, object] = {}

    class FakeClient:
        def __init__(self, base_url: str, api_key: str):
            calls["client_init"] = (base_url, api_key)

        def create_project(self, name: str, description: str | None = None):
            calls["create_project"] = (name, description)
            return {"project_id": "11111111-1111-1111-1111-111111111111"}

        def upload_artifacts(self, **kwargs):
            calls["upload_artifacts"] = kwargs
            return {"version_id": "22222222-2222-2222-2222-222222222222"}

    monkeypatch.setattr("sanityops_cli.api.client.SanityopsClient", FakeClient)

    res = ExtractionResult(
        artifacts=[
            ExtractedArtifact(
                type="prompt",
                name="sys",
                content="Hello prompt",
                completeness="full original",
                L="AC-L1",
                source=str(proj_dir / "prompt.md"),
            )
        ]
    )

    _auto_upload(None, res, config_path=cfg_path)

    assert calls["client_init"] == ("http://localhost:3000/", "dl-test-key")
    assert calls["create_project"] == ("custom-agent", None)
    saved = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert saved["project"]["id"] == "11111111-1111-1111-1111-111111111111"
    assert saved["project"]["name"] == "custom-agent"


def test_banner_line_contains_version_python_and_platform():
    from sanityops_cli import __version__
    from sanityops_cli.commands.inspect import _banner_line

    banner = _banner_line()
    assert f"sanityops-cli v{__version__}" in banner
    assert "Python" in banner


def test_inspect_prints_banner_and_log_path(monkeypatch, tmp_path):
    """The run header shows the banner and the log file path."""
    harness = Harness(monkeypatch, tmp_path)
    result = harness.run(tmp_path)
    assert result.exit_code == 0, result.output
    assert "sanityops-cli v" in result.output
    assert "Log file:" in result.output
