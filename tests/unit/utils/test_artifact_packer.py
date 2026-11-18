"""Unit tests for ArtifactPacker (path-based packing, push command)."""

import json
import zipfile
from io import BytesIO
from pathlib import Path

from sanityops_cli.utils.artifact_packer import ArtifactPacker


class TestPackFromPaths:
    """Tests for path-based packing (push command)."""

    def test_single_prompt_from_path(self, tmp_path: Path):
        """Test packing a single prompt file by path."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Hello, world!")

        packer = ArtifactPacker([str(prompt_file)], [], [])
        result = packer.pack()

        assert result["prompt_content"] is not None
        assert "Hello, world!" in result["prompt_content"]

    def test_multiple_prompts_from_paths(self, tmp_path: Path):
        """Test packing multiple prompt files by paths."""
        prompt1 = tmp_path / "prompt1.md"
        prompt1.write_text("First prompt")
        prompt2 = tmp_path / "prompt2.md"
        prompt2.write_text("Second prompt")

        packer = ArtifactPacker([str(prompt1), str(prompt2)], [], [])
        result = packer.pack()

        assert "First prompt" in result["prompt_content"]
        assert "Second prompt" in result["prompt_content"]

    def test_single_tool_from_path(self, tmp_path: Path):
        """Test packing a single tool file by path."""
        tool_file = tmp_path / "tool.json"
        tool_file.write_text(
            json.dumps(
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {"type": "object"},
                }
            )
        )

        packer = ArtifactPacker([], [str(tool_file)], [])
        result = packer.pack()

        assert result["tools_schema"] is not None
        tools = json.loads(result["tools_schema"])
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"

    def test_tool_array_from_path(self, tmp_path: Path):
        """Test packing a file containing an array of tools."""
        tool_file = tmp_path / "tools.json"
        tool_file.write_text(
            json.dumps(
                [
                    {"name": "tool1", "description": "First"},
                    {"name": "tool2", "description": "Second"},
                ]
            )
        )

        packer = ArtifactPacker([], [str(tool_file)], [])
        result = packer.pack()

        tools = json.loads(result["tools_schema"])
        assert len(tools) == 2

    def test_tool_dedup_by_name(self, tmp_path: Path):
        """Test that tools are deduplicated by name."""
        tool1 = tmp_path / "tool1.json"
        tool1.write_text(json.dumps({"name": "shared", "version": 1}))
        tool2 = tmp_path / "tool2.json"
        tool2.write_text(json.dumps({"name": "shared", "version": 2}))

        packer = ArtifactPacker([], [str(tool1), str(tool2)], [])
        result = packer.pack()

        tools = json.loads(result["tools_schema"])
        assert len(tools) == 1
        # Uses the last definition
        assert tools[0]["version"] == 2

    def test_tool_openai_format_normalized_to_flat(self, tmp_path: Path):
        """pack() must normalize OpenAI-wrapped tools to the flat format.

        push (paths) and inspect (findings) must upload the same
        provider-neutral structure: the OpenAI {type, function} wrapper is
        stripped here, matching _pack_tools_from_findings.
        """
        tool_file = tmp_path / "tools.json"
        tool_file.write_text(
            json.dumps(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "search_tools",
                            "description": "Search tools",
                            "parameters": {"type": "object"},
                        },
                    },
                    {"name": "flat_tool", "description": "Already flat"},
                ]
            )
        )

        packer = ArtifactPacker([], [str(tool_file)], [])
        result = packer.pack()

        tools = json.loads(result["tools_schema"])
        assert tools == [
            {
                "name": "search_tools",
                "description": "Search tools",
                "parameters": {"type": "object"},
            },
            {"name": "flat_tool", "description": "Already flat"},
        ]

    def test_skill_file_from_path(self, tmp_path: Path):
        """Test packing a single skill file by path."""
        skill_file = tmp_path / "skill.md"
        skill_file.write_text("---\nname: test\n---\nContent")

        packer = ArtifactPacker([], [], [str(skill_file)])
        result = packer.pack()

        assert result["skill_file"] is not None
        filename, content = result["skill_file"]
        assert filename == "skills.zip"

        with zipfile.ZipFile(BytesIO(content)) as zf:
            names = zf.namelist()
            assert any("skill.md" in n for n in names)

    def test_skill_directory_from_path(self, tmp_path: Path):
        """Test packing a skill directory by path."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("---\nname: test\n---\nContent")
        (skill_dir / "references.md").write_text("References")

        packer = ArtifactPacker([], [], [str(skill_dir)])
        result = packer.pack()

        filename, content = result["skill_file"]

        with zipfile.ZipFile(BytesIO(content)) as zf:
            names = zf.namelist()
            assert any("SKILL.md" in n for n in names)
            assert any("references.md" in n for n in names)

    def test_skill_directory_skip_dependency_dirs(self, tmp_path: Path):
        """Test that node_modules and __pycache__ are skipped when packing by path."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("skill")

        # Create node_modules
        node_modules = skill_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}")

        # Create __pycache__
        pycache = skill_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "module.pyc").write_text("binary")

        packer = ArtifactPacker([], [], [str(skill_dir)])
        result = packer.pack()

        filename, content = result["skill_file"]

        with zipfile.ZipFile(BytesIO(content)) as zf:
            names = zf.namelist()
            assert any("SKILL.md" in n for n in names)
            assert not any("node_modules" in n for n in names)
            assert not any("__pycache__" in n for n in names)

    def test_pack_all_from_paths(self, tmp_path: Path):
        """Test packing all artifact types by paths."""
        prompt = tmp_path / "prompt.md"
        prompt.write_text("Test prompt")

        tool = tmp_path / "tool.json"
        tool.write_text(json.dumps({"name": "test_tool"}))

        skill = tmp_path / "skill.md"
        skill.write_text("Test skill")

        packer = ArtifactPacker([str(prompt)], [str(tool)], [str(skill)])
        result = packer.pack()

        assert result["prompt_content"] is not None
        assert result["tools_schema"] is not None
        assert result["skill_file"] is not None

    def test_yaml_tools_and_input_schema_normalized(self, tmp_path: Path):
        """YAML tool registries and inputSchema/input_schema normalize to parameters."""
        tool_yaml = tmp_path / "tools.yaml"
        tool_yaml.write_text(
            "tools:\n"
            "  - name: mcp_tool\n"
            "    description: MCP schema\n"
            "    inputSchema:\n"
            "      type: object\n"
            "  - name: anthropic_tool\n"
            "    description: Anthropic schema\n"
            "    input_schema:\n"
            "      type: object\n",
            encoding="utf-8",
        )

        packer = ArtifactPacker([], [str(tool_yaml)], [])
        tools = json.loads(packer.pack()["tools_schema"])
        assert tools == [
            {
                "name": "mcp_tool",
                "description": "MCP schema",
                "parameters": {"type": "object"},
            },
            {
                "name": "anthropic_tool",
                "description": "Anthropic schema",
                "parameters": {"type": "object"},
            },
        ]

    def test_skill_dir_under_hidden_ancestor_packs_files(self, tmp_path: Path):
        """Hidden ancestor directories must not cause skill files to be skipped."""
        skill_dir = tmp_path / ".hidden_workspace" / "skills" / "demo-skill"
        (skill_dir / "references").mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n")
        (skill_dir / "references" / "guide.md").write_text("guide")
        (skill_dir / ".secret").write_text("skip")

        packer = ArtifactPacker([], [], [str(skill_dir)])
        _, blob = packer.pack()["skill_file"]
        with zipfile.ZipFile(BytesIO(blob)) as zf:
            names = set(zf.namelist())
        assert names == {"demo-skill/SKILL.md", "demo-skill/references/guide.md"}

    def test_skill_md_path_includes_sibling_resource_subdirs(self, tmp_path: Path):
        """Expanded SKILL.md paths pack adjacent references/scripts/skill.yaml."""
        skill_dir = tmp_path / "skills" / "maintenance"
        (skill_dir / "references").mkdir(parents=True)
        (skill_dir / "scripts").mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: maintenance\ndescription: d\n---\n")
        (skill_dir / "skill.yaml").write_text("name: maintenance\n")
        (skill_dir / "references" / "notes.md").write_text("notes")
        (skill_dir / "scripts" / "check.py").write_text("print('ok')")

        packer = ArtifactPacker([], [], [str(skill_md)])
        _, blob = packer.pack()["skill_file"]
        with zipfile.ZipFile(BytesIO(blob)) as zf:
            names = set(zf.namelist())
        assert names == {
            "maintenance/SKILL.md",
            "maintenance/skill.yaml",
            "maintenance/references/notes.md",
            "maintenance/scripts/check.py",
        }


class TestPackEmpty:
    def test_empty_result(self):
        """Empty manifests produce an all-None payload."""
        packer = ArtifactPacker([], [], [])
        result = packer.pack()

        assert result["prompt_content"] is None
        assert result["tools_schema"] is None
        assert result["skill_file"] is None
