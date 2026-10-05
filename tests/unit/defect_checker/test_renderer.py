"""Unit tests for DefectRenderer."""

from rich.console import Console

from sanityops_cli.defect_checker.renderer import FULL_EXPERIENCE_URL, DefectRenderer


def _result(results, summary=None):
    return {
        "status": "completed",
        "results": results,
        "summary": summary
        or {
            "total_defects": 0,
            "p0_count": 0,
            "p1_count": 0,
            "p2_count": 0,
            "gate_result": "PASS",
        },
        "errors": [],
        "metadata": {},
    }


def _qds_defect(defect_id, severity, name="n", location="loc", impact="imp", fix="fix"):
    return {
        "id": defect_id,
        "name": name,
        "severity": severity,
        "category": "cat",
        "description": "desc",
        "location": location,
        "impact": impact,
        "fix_suggestion": fix,
        "artifact_refs": ["/proj/skills/s.md"],
    }


class TestRender:
    def test_footer_contains_server_url(self):
        console = Console(record=True, width=80)
        DefectRenderer(console).render(_result([]))
        out = console.export_text()
        assert FULL_EXPERIENCE_URL in out
        assert "For the full experience" in out

    def test_footer_can_show_report_path(self):
        console = Console(record=True, width=80)
        DefectRenderer(console).render(
            _result([]), report_path="/tmp/reports/inspect-20260909-103045.md"
        )
        out = console.export_text()
        assert "Report saved to" in out
        assert "/tmp/reports/inspect-20260909-103045.md" in out

    def test_shows_summary_counts(self):
        console = Console(record=True, width=80)
        result = _result(
            [],
            summary={
                "total_defects": 5,
                "p0_count": 1,
                "p1_count": 2,
                "p2_count": 2,
                "gate_result": "FAIL",
            },
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Total defects" in out and "5" in out
        assert "Gate" in out and "FAIL" in out

    def test_group_labeled_by_module(self):
        console = Console(record=True, width=80)
        result = _result(
            [
                {
                    "module": "QDS",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [_qds_defect("d1", "P0")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Skills" in out

    def test_only_two_defects_shown_with_notice(self):
        console = Console(record=True, width=80)
        result = _result(
            [
                {
                    "module": "QDS",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [
                        _qds_defect("d1", "P0"),
                        _qds_defect("d2", "P1"),
                        _qds_defect("d3", "P2"),
                    ],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "d1" in out
        assert "d2" in out
        assert "d3" not in out
        assert "1 more defects not shown" in out

    def test_group_without_defects_not_rendered(self):
        console = Console(record=True, width=80)
        result = _result([{"module": "QDT", "status": "completed", "artifacts": [], "defects": []}])
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Tools" not in out

    def test_cross_module_rendered(self):
        """CROSS module defects are now rendered."""
        console = Console(record=True, width=80)
        result = _result(
            [
                {
                    "module": "CROSS",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [_qds_defect("c1", "P0")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "c1" in out
        assert "Cross" in out


class TestResolveArtifactNames:
    def test_single_artifact_with_ref(self):
        """Returns artifact name when artifact_refs matches one artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_multiple_artifacts_with_refs(self):
        """Returns comma-separated names when multiple artifact_refs."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": [
                {"artifact_refs": ["skill-1", "skill-2"]},
            ],
        }
        assert _resolve_artifact_names(result) == "morning-report, daily-summary"

    def test_fallback_single_artifact_no_refs(self):
        """Returns single artifact name when no artifact_refs but only one artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": []}],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_returns_none_no_refs_multiple_artifacts(self):
        """Returns None when no artifact_refs and multiple artifacts."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": [{"artifact_refs": []}],
        }
        assert _resolve_artifact_names(result) is None

    def test_deduplicates_refs(self):
        """Deduplicates artifact_refs pointing to same artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [
                {"artifact_refs": ["skill-1"]},
                {"artifact_refs": ["skill-1"]},
            ],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_skips_non_dict_defects(self):
        """Skips defects that are not dicts instead of raising AttributeError."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [
                None,
                "not-a-dict",
                {"artifact_refs": ["skill-1"]},
            ],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_non_dict_defects_only_returns_none(self):
        """Returns None when every defect is a non-dict."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": [None, 42],
        }
        assert _resolve_artifact_names(result) is None

    def test_missing_defects_key(self):
        """Handles a result with no defects key at all."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {"artifacts": [{"id": "skill-1", "name": "morning-report"}]}
        assert _resolve_artifact_names(result) == "morning-report"

    def test_none_defects_key(self):
        """Handles an explicit None defects value."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": None,
        }
        assert _resolve_artifact_names(result) is None

    def test_artifact_without_name_key(self):
        """Skips artifacts that have no name; falls back to plural label."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1"}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert _resolve_artifact_names(result) is None

    def test_artifact_with_none_name(self):
        """Skips artifacts whose name is None."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names

        result = {
            "artifacts": [{"id": "skill-1", "name": None}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert _resolve_artifact_names(result) is None


class TestResolveArtifactTitle:
    def test_qds_with_resolvable_names(self):
        """Returns 'Skill <name>' when QDS module with resolvable artifact."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title

        result = {
            "module": "QDS",
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert resolve_artifact_title(result) == "Skill morning-report"

    def test_qdt_without_resolvable_names(self):
        """Returns plural label when QDT module without resolvable names."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title

        result = {
            "module": "QDT",
            "artifacts": [],
            "defects": [],
        }
        assert resolve_artifact_title(result) == "Tools"

    def test_cross_module(self):
        """Returns 'Cross' for CROSS module."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title

        result = {"module": "CROSS"}
        assert resolve_artifact_title(result) == "Cross"

    def test_unknown_module(self):
        """Returns None for unknown modules."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title

        result = {"module": "UNKNOWN"}
        assert resolve_artifact_title(result) is None

    def test_missing_module_key(self):
        """Returns None when module key is missing entirely."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title

        result = {"artifacts": [{"id": "skill-1", "name": "morning-report"}]}
        assert resolve_artifact_title(result) is None


class TestPermissionDefects:
    """Tests for QD-PM permission defect rendering."""

    def _permission_defect(
        self,
        defect_id="QD-PM-1.1",
        severity="P0",
        name="Permission overflow",
        location="skill.md:15",
        impact="Excessive read access",
        fix="Narrow permission scope",
        action="read",
        permission_side="skill -> tool -> params",
        duty_side="skill -> para.3 -> stmt.1",
    ):
        """Create a permission defect dict for testing."""
        return {
            "id": defect_id,
            "name": name,
            "severity": severity,
            "category": "permission",
            "description": "Permission exceeds duty boundary",
            "location": location,
            "impact": impact,
            "fix_suggestion": fix,
            "details": {
                "action": action,
                "permission_side": permission_side,
                "duty_side": duty_side,
            },
        }

    def test_qdpm_module_rendered(self):
        """QD-PM module is rendered with 'Permissions' label."""
        console = Console(record=True, width=100)
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [self._permission_defect()],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Permissions" in out
        assert "QD-PM-1.1" in out

    def test_permission_defect_shows_action_field(self):
        """Permission defects show action field in terminal."""
        console = Console(record=True, width=100)
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [self._permission_defect(action="write")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Action" in out
        assert "write" in out

    def test_permission_defect_shows_permission_side(self):
        """Permission defects show permission_side field."""
        console = Console(record=True, width=120)
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [self._permission_defect(permission_side="skill -> tool -> file")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Permission" in out and "skill -> tool -> file" in out

    def test_permission_defect_shows_duty_side(self):
        """Permission defects show duty_side field."""
        console = Console(record=True, width=120)
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [self._permission_defect(duty_side="skill -> para.5")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Duty" in out and "skill -> para.5" in out

    def test_permission_defect_without_details(self):
        """Permission defects without details field still render."""
        console = Console(record=True, width=100)
        defect = {
            "id": "QD-PM-2.1",
            "name": "Permission issue",
            "severity": "P1",
            "category": "permission",
            "description": "desc",
            "location": "skill.md:20",
            "impact": "impact",
            "fix_suggestion": "fix",
            # No details dict
        }
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [defect],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "QD-PM-2.1" in out
        assert "Location" in out

    def test_permission_defect_with_empty_details(self):
        """Permission defects with empty details dict render gracefully."""
        console = Console(record=True, width=100)
        defect = {
            "id": "QD-PM-3.1",
            "name": "Permission issue",
            "severity": "P1",
            "category": "permission",
            "description": "desc",
            "location": "skill.md:30",
            "details": {},  # Empty dict
        }
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [defect],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "QD-PM-3.1" in out
        # Should not crash, should show standard fields

    def test_permission_defect_detected_by_id_prefix(self):
        """Permission defect detected by QD-PM ID prefix even with different module.

        This tests the ID prefix fallback detection path.
        """
        console = Console(record=True, width=100)
        defect = {
            "id": "QD-PM-4.1",  # ID starts with QD-PM
            "name": "Permission issue",
            "severity": "P1",
            "category": "",  # No category
            "description": "desc",
            "details": {"action": "read"},
        }
        result = _result(
            [
                {
                    "module": "QDS",  # Different module - tests ID prefix detection
                    "status": "completed",
                    "artifacts": [],
                    "defects": [defect],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        # Should use permission format due to ID prefix
        assert "Action" in out
        assert "read" in out

    def test_permission_defect_detected_by_category(self):
        """Permission defect detected by category='permission' with non-QD-PM module and ID.

        This tests the category-based fallback detection path.
        """
        console = Console(record=True, width=100)
        defect = {
            "id": "MISC-1",  # Not QD-PM prefix
            "name": "Permission issue",
            "severity": "P1",
            "category": "permission",  # Category triggers detection
            "description": "desc",
            "details": {"action": "write"},
        }
        result = _result(
            [
                {
                    "module": "QDT",  # Different module - tests category detection
                    "status": "completed",
                    "artifacts": [],
                    "defects": [defect],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        # Should use permission format due to category
        assert "Action" in out
        assert "write" in out

    def test_permission_defect_shows_name_field(self):
        """Permission defects show name field for consistency with markdown."""
        console = Console(record=True, width=100)
        result = _result(
            [
                {
                    "module": "QD-PM",
                    "status": "completed",
                    "artifacts": [],
                    "defects": [self._permission_defect(name="Permission overflow")],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        assert "Name" in out
        assert "Permission overflow" in out

    def test_permission_format_used_when_module_is_qdpm(self):
        """Permission format used when module is QD-PM, even with non-matching ID/category.

        This tests the edge case where module == "QD-PM" but defect ID doesn't start
        with QD-PM and category is empty - ensuring terminal and markdown stay consistent.
        """
        console = Console(record=True, width=100)
        defect = {
            "id": "OTHER-1",  # Not QD-PM prefix
            "name": "Edge case defect",
            "severity": "P1",
            "category": "",  # Empty category
            "details": {"action": "read"},
        }
        result = _result(
            [
                {
                    "module": "QD-PM",  # Module is QD-PM
                    "status": "completed",
                    "artifacts": [],
                    "defects": [defect],
                }
            ]
        )
        DefectRenderer(console).render(result)
        out = console.export_text()
        # Should still use permission format due to module == "QD-PM"
        assert "Action" in out
        assert "read" in out
