"""Meta-test: RULE_DEFINITIONS must mirror the vendored checklist v2 index.

The 17-item registry (ID / Name / severity) is diffed against the checklist
tables in ``src/sanityops_cli/skills/code-contract-checklist.v2.md`` §2-§6;
items in §3-§6 additionally carry an engine column that must match the
registry's ``engine`` field (design §7).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import sanityops_cli
from sanityops_cli.code_contract_checker.models import (
    HYBRID_RULE_IDS,
    RULE_DEFINITIONS,
    QCRuleID,
    Severity,
)

CHECKLIST_PATH = Path(sanityops_cli.__file__).parent / "skills" / "code-contract-checklist.v2.md"

SEVERITIES = {"P0", "P1", "P2"}
ENGINES = {"Automated", "Semi-automated", "Pattern match"}

# Engine column only exists in §3-§6; §2 (QC-0.x) has no engine in the
# checklist and the registry follows design §7.1's program/hybrid split.
EXPECTED_ENGINES = {
    "QC-0.1": None,
    "QC-0.2": None,
    "QC-0.3": None,
    "QC-0.4": None,
    "QC-0.5": None,
    "QC-1.1": "Automated",
    "QC-1.2": "Automated",
    "QC-1.3": "Semi-automated",
    "QC-1.4": "Automated",
    "QC-2.1": "Pattern match",
    "QC-2.2": "Pattern match",
    "QC-2.3": "Pattern match",
    "QC-3.1": "Automated",
    "QC-3.2": "Automated",
    "QC-3.3": "Pattern match",
    "QC-4.1": "Semi-automated",
    "QC-4.2": "Semi-automated",
}


def parse_checklist(path: Path) -> dict[str, tuple[str, str, str | None]]:
    """Extract (name, severity, engine) per rule ID from checklist.

    The 17-item checklist in v2 lists all rules under section 2.
    """
    entries: dict[str, tuple[str, str, str | None]] = {}
    section: int | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        header = re.match(r"^## (\d+)\.", line)
        if header:
            section = int(header.group(1))
            continue
        if line.startswith("## "):
            section = None
            continue
        if section != 2 or not line.startswith("| QC-"):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rule_id = cells[0]
        name = cells[1]
        severity = next((cell for cell in cells if cell in SEVERITIES), None)
        if not severity:
            continue
        engine = cells[-1] if cells[-1] in ENGINES else None
        entries[rule_id] = (name, severity, engine)

    return entries


@pytest.fixture(scope="module")
def checklist() -> dict[str, tuple[str, str, str | None]]:
    assert CHECKLIST_PATH.exists(), f"vendored checklist missing at {CHECKLIST_PATH}"
    parsed = parse_checklist(CHECKLIST_PATH)
    assert len(parsed) == 17, f"checklist index parse got {len(parsed)} items"
    return parsed


class TestRegistryMatchesChecklist:
    def test_17_rule_ids(self):
        assert len(QCRuleID) == 17
        assert set(RULE_DEFINITIONS) == set(QCRuleID)

    def test_ids_match_checklist(self, checklist):
        assert {str(rid) for rid in RULE_DEFINITIONS} == set(checklist)

    @pytest.mark.parametrize("rid", sorted(str(r) for r in QCRuleID))
    def test_name_and_severity_verbatim(self, checklist, rid):
        entry = RULE_DEFINITIONS[QCRuleID(rid)]
        expected_name, expected_severity, _ = checklist[rid]
        assert entry["name"] == expected_name, f"{rid} name drift"
        assert entry["severity"] == Severity(expected_severity), f"{rid} severity drift"

    @pytest.mark.parametrize("rid", sorted(str(r) for r in QCRuleID))
    def test_engine_matches_checklist(self, checklist, rid):
        _, _, checklist_engine = checklist[rid]
        registry_engine = RULE_DEFINITIONS[QCRuleID(rid)]["engine"]
        if checklist_engine is None:
            # QC-0.x rows have no engine column in the checklist §2; the
            # registry assigns one from design §7.1 — assert internal
            # consistency with the hybrid flag instead of a checklist value.
            assert registry_engine == EXPECTED_ENGINES[rid] or registry_engine in ENGINES
            assert (registry_engine == "Semi-automated") == RULE_DEFINITIONS[QCRuleID(rid)][
                "hybrid"
            ]
        else:
            assert checklist_engine == EXPECTED_ENGINES[rid]
            assert registry_engine == checklist_engine


class TestHybridSplit:
    def test_exactly_four_hybrid_rules(self):
        assert {str(rid) for rid in HYBRID_RULE_IDS} == {"QC-0.5", "QC-1.3", "QC-4.1", "QC-4.2"}

    def test_hybrid_flag_consistent_with_engine(self):
        for rid, meta in RULE_DEFINITIONS.items():
            assert meta["hybrid"] == (meta["engine"] == "Semi-automated"), str(rid)
