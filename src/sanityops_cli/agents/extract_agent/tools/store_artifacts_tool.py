"""The ExtractAgent's sole output channel.

Implements the chunked-delivery protocol from the skill-based inspect design
(§5.2–§5.3). The tool is the integrity authority: chunk sequences are
validated as they arrive, and the CLI reads finalized records from the tool
instance (instance state, not ClassVar) after the agent run ends.

Delivery contract surfaced to the LLM (mirrored by the contract appendix):

- ``add_artifact`` — upsert one chunk of an artifact record. First chunk must
  declare ``total_chunks``; ``seq`` must arrive in order; ``final=true`` only
  on ``seq == total_chunks - 1`` and must carry the record metadata
  (completeness/L/evidence/...). Re-sending from ``seq=0`` replaces the
  earlier stream (last complete stream wins) — but only once the restart
  itself validates, so a malformed restart never destroys a good stream.
- ``add_reference`` — one reference-layer record.
- ``set_attribution`` — the set-level attribution statement.
- ``list`` — read-only resync of everything stored so far.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aidynamic_agent.tools.base import Tool, ToolResult
from pydantic import ValidationError

from deeplogic_cli.inspect_pipeline.models import (
    ARTIFACT_TYPES,
    ATTRIBUTION_STATUSES,
    COMPLETENESS_LABELS,
    L_LEVELS,
    Attribution,
    ExtractedArtifact,
    ExtractedReference,
)

#: Recommended content chars per chunk. 6000 chars ≈ 1500 tokens on the
#: chars/4 heuristic and stays safe for CJK (≈1 token/char → 6000 tokens, still
#: well under the provider's 8192-token output ceiling together with tool-call
#: overhead). This is *advice* surfaced to the model, not a hard rejection:
#: once the model has already emitted an oversized chunk, rejecting it only
#: burns another full round-trip, so chunks up to MAX_CHUNK_HARD_CHARS are
#: accepted as-is.
MAX_CHUNK_CHARS = 6000

#: Hard ceiling per chunk; beyond this the call is rejected with concrete
#: split points so the model can retry in one shot.
MAX_CHUNK_HARD_CHARS = 30000

_EXAMPLE_TWO_CHUNKS = (
    'Example for a 2-chunk artifact — chunk 0: {"type":"prompt","name":"x",'
    '"content":"<first part>","seq":0,"total_chunks":2}; chunk 1: {"type":"prompt",'
    '"name":"x","content":"<rest>","seq":1,"total_chunks":2,"final":true,'
    '"completeness":"full original","L":"AC-L2","source":"/abs/path"}'
)


def _coerce_dict(value: object) -> dict:
    """Tolerate models that pass an object argument as a JSON string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _split_points(length: int, size: int = MAX_CHUNK_CHARS) -> str:
    bounds = list(range(0, length, size)) + [length]
    return ", ".join(f"[{a}:{b}]" for a, b in zip(bounds, bounds[1:], strict=False))


@dataclass
class _ChunkState:
    chunks: list[str] = field(default_factory=list)
    total_chunks: int | None = None
    record: ExtractedArtifact | None = None
    source: str = ""
    resends: int = 0


class StoreArtifactsTool(Tool):
    """Structured output channel for the ExtractAgent.

    One instance per agent run; the CLI reads ``finalize()`` from the same
    instance it registered, so state is intentionally per-instance.
    """

    name = "store_artifacts"
    description = (
        "Store extraction results: artifact records (chunked for oversized "
        "content), cross-artifact references, and the set-level attribution "
        "statement. This is the only way to report extracted artifacts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add_artifact", "add_reference", "set_attribution", "list"],
                "description": "Which store operation to perform.",
            },
            "artifact": {
                "type": "object",
                "description": "Required for add_artifact. One chunk of an artifact record.",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": list(ARTIFACT_TYPES),
                        "description": "Artifact type.",
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Artifact name (the upsert key together with type).",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Verbatim artifact text for this chunk. For type='tool' "
                            "you may omit content and deliver the parsed schema object."
                        ),
                    },
                    "content_from_source": {
                        "type": "boolean",
                        "description": (
                            "Set true when the artifact is the ENTIRE source file, verbatim "
                            "(e.g. a whole prompt or SKILL.md). The tool reads `source` and "
                            "fills the content itself — omit `content` and use total_chunks=1, "
                            "final=true. Do not use when the file holds several artifacts."
                        ),
                    },
                    "schema": {
                        "type": "object",
                        "description": (
                            "The parsed tool schema as a JSON object. Required for "
                            "inspectable tools; do not stringify it."
                        ),
                    },
                    "completeness": {
                        "type": "string",
                        "enum": list(COMPLETENESS_LABELS),
                        "description": "Completeness label (exact six labels).",
                    },
                    "L": {
                        "type": "string",
                        "enum": list(L_LEVELS),
                        "description": (
                            "Assigned level; 'undetermined' when facts are "
                            "insufficient. L4 is rejected."
                        ),
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Verbatim head/tail source excerpt proving the extraction.",
                    },
                    "field_evidence": {
                        "type": "array",
                        "description": "Per-field provenance; required when completeness='assembled'.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string"},
                                "snippet": {"type": "string"},
                            },
                            "required": ["field", "snippet"],
                        },
                    },
                    "source": {
                        "type": "string",
                        "description": "Absolute path of the source file.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Required when completeness='not inspectable'.",
                    },
                    "seq": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "0-based chunk sequence number.",
                    },
                    "total_chunks": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Total number of chunks; declare on the first chunk.",
                    },
                    "final": {
                        "type": "boolean",
                        "description": "True only on the last chunk (seq == total_chunks - 1).",
                    },
                },
                "required": ["type", "name"],
            },
            "reference": {
                "type": "object",
                "description": "Required for add_reference.",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "referenced_by": {"type": "string", "minLength": 1},
                    "relationship": {"type": "string", "minLength": 1},
                },
                "required": ["name", "referenced_by", "relationship"],
            },
            "attribution": {
                "type": "object",
                "description": "Required for set_attribution.",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": list(ATTRIBUTION_STATUSES),
                        "description": "'single' (one agent's set) or 'pending' (unresolved).",
                    },
                    "note": {"type": "string"},
                },
                "required": ["status"],
            },
        },
        "required": ["operation"],
    }
    tags = ["extract", "store"]

    def __init__(self, allowed_roots: list[Path] | None = None) -> None:
        super().__init__()
        self._allowed_roots = [Path(r).resolve() for r in (allowed_roots or [])]
        self._streams: dict[tuple[str, str], _ChunkState] = {}
        self._references: list[ExtractedReference] = []
        self._attribution: Attribution | None = None
        self._resend_log: list[str] = []
        self._rejected_chunks: dict[tuple[str, str], set[int]] = {}
        self._recovered: set[tuple[str, str]] = set()
        self._candidates: list[dict] = []

    # ------------------------------------------------------------------
    # Tool entry
    # ------------------------------------------------------------------

    async def execute(self, **kwargs) -> ToolResult:  # noqa: ANN003
        operation = kwargs.get("operation")
        if operation == "add_artifact":
            artifact = _coerce_dict(kwargs.get("artifact"))
            result = self._add_artifact(artifact)
            if not result.success:
                a_type, name = artifact.get("type"), artifact.get("name")
                if a_type in ARTIFACT_TYPES and isinstance(name, str) and name:
                    rejected = self._rejected_chunks.setdefault((a_type, name), set())
                    seq = artifact.get("seq", 0)
                    if isinstance(seq, int):
                        rejected.add(seq)
            return result
        if operation == "add_reference":
            return self._add_reference(_coerce_dict(kwargs.get("reference")))
        if operation == "set_attribution":
            return self._set_attribution(_coerce_dict(kwargs.get("attribution")))
        if operation == "list":
            return self._list()
        return self._error(f"unknown operation '{operation}'")

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _add_artifact(self, artifact: dict) -> ToolResult:
        for required in ("type", "name"):
            if not isinstance(artifact.get(required), str) or not artifact[required]:
                return self._error(f"artifact.{required} is required")
        a_type, name = artifact["type"], artifact["name"]
        if a_type not in ARTIFACT_TYPES:
            return self._error(f"artifact.type must be one of {ARTIFACT_TYPES}, got {a_type!r}")

        if artifact.get("content_from_source"):
            loaded = self._load_source_content(artifact)
            if isinstance(loaded, ToolResult):
                return loaded
            artifact = {**artifact, "content": loaded, "seq": 0, "total_chunks": 1, "final": True}

        seq = artifact.get("seq", 0)
        if not isinstance(seq, int) or seq < 0:
            return self._error(f"artifact.seq must be a non-negative integer, got {seq!r}")

        key = (a_type, name)
        existing = self._streams.get(key)
        is_restart = existing is not None and seq == 0 and len(existing.chunks) > 0

        # Basic per-chunk validation (enum values, field bindings) before any
        # state mutation: a malformed restart must never destroy a good stream.
        meta_error = self._validate_chunk(artifact, final=False)
        if meta_error:
            return self._error(meta_error)

        if is_restart and existing is not None:
            state = _ChunkState(resends=existing.resends + 1)
        elif existing is not None:
            state = existing
        else:
            if seq != 0:
                return self._error(
                    f"artifact {a_type}/{name}: first chunk must have seq=0, got {seq}"
                )
            state = _ChunkState()

        total = state.total_chunks
        if total is None:
            total = artifact.get("total_chunks")
            if total is None and artifact.get("final") and seq == 0:
                total = 1  # single-chunk delivery that forgot total_chunks
            if not isinstance(total, int) or total < 1:
                return self._error(
                    f"artifact {a_type}/{name}: first chunk must declare total_chunks >= 1. "
                    + _EXAMPLE_TWO_CHUNKS
                )

        if seq != len(state.chunks):
            return self._error(
                f"artifact {a_type}/{name}: expected chunk {len(state.chunks)}, got seq={seq}; "
                f"retransmit from seq=0 to restart"
            )

        content = artifact.get("content", "")
        # A metadata-only final chunk is fine when earlier chunks hold the text.
        trailing_meta_only = bool(artifact.get("final")) and seq > 0 and bool(state.chunks)
        if not content and not artifact.get("schema") and not trailing_meta_only:
            return self._error(
                f"artifact {a_type}/{name}: chunk {seq} needs content or schema. "
                "Put the text in `content`; the final chunk may omit it only if earlier "
                "chunks already carried the whole text."
            )
        if len(content) > MAX_CHUNK_HARD_CHARS:
            return self._error(
                f"artifact {a_type}/{name}: chunk {seq} content is {len(content)} chars "
                f"(hard limit {MAX_CHUNK_HARD_CHARS}). Split it at {_split_points(len(content))} "
                f"(~{MAX_CHUNK_CHARS} chars each), set total_chunks to the number of pieces, "
                f"and send seq=0.. in order. " + _EXAMPLE_TWO_CHUNKS
            )

        is_last = seq == total - 1
        if is_last and not artifact.get("final"):
            return self._error(
                f"artifact {a_type}/{name}: chunk {seq} is the last of "
                f"{total}; set final=true on it"
            )
        if not is_last and artifact.get("final"):
            # The model decided this is the end: honour it (seq is contiguous at
            # this point) rather than burning a retry on a counting mistake.
            total = seq + 1
            is_last = True

        record = None
        if is_last:
            # The final chunk carries the record metadata; validate it as such.
            final_error = self._validate_chunk(artifact, final=True)
            if final_error:
                return self._error(final_error)

            chunks = [*state.chunks, content]
            try:
                record = ExtractedArtifact(
                    type=a_type,
                    name=name,
                    content="\n".join(chunks) if any(chunks) else "",
                    schema=artifact.get("schema") or {},
                    completeness=artifact["completeness"],
                    L=artifact["L"],
                    evidence=artifact.get("evidence", ""),
                    field_evidence=artifact.get("field_evidence") or [],
                    source=artifact["source"],
                    reason=artifact.get("reason", ""),
                )
            except ValidationError as exc:
                details = "; ".join(error["msg"] for error in exc.errors())
                return self._error(
                    f"artifact {a_type}/{name}: {details}. Correct and resend seq={seq}."
                )

        # ---- state mutations only after every check passed ----
        self._streams[key] = state
        rejected = self._rejected_chunks.get(key)
        if is_restart or (rejected is not None and (seq in rejected or existing is None)):
            self._resend_log.append(f"{a_type}/{name}")
        if rejected is not None:
            rejected.discard(seq)
        state.total_chunks = total
        state.chunks.append(content)
        state.source = artifact.get("source", state.source)
        if is_last:
            state.record = record
            recovered = self._rejected_chunks.pop(key, None) is not None
            if recovered:
                self._recovered.add(key)
            ack = f"stored artifact {name} chunk {seq + 1}/{state.total_chunks}; artifact complete"
            return self._ok(ack, recovered=recovered)
        ack = (
            f"stored artifact {name} chunk {seq + 1}/{state.total_chunks}; "
            f"next expected: {len(state.chunks)}"
        )
        return self._ok(ack, next_expected=len(state.chunks))

    def _validate_chunk(self, artifact: dict, *, final: bool) -> str | None:
        completeness = artifact.get("completeness")
        if completeness is not None and completeness not in COMPLETENESS_LABELS:
            return (
                f"completeness must be one of {COMPLETENESS_LABELS}, got {completeness!r}; "
                f"note the exact separator in 'original · variable unexpanded' (U+00B7)"
            )
        level = artifact.get("L")
        if level is not None and level not in L_LEVELS:
            return f"L must be one of {L_LEVELS}, got {level!r}"
        if artifact.get("type") == "tool":
            schema = artifact.get("schema")
            if schema is not None and not isinstance(schema, dict):
                return "artifact.schema must be a JSON object (do not stringify it)"
        if completeness == "assembled":
            fe = artifact.get("field_evidence") or []
            if not fe:
                return "field_evidence is required when completeness='assembled'"
            for item in fe:
                if not isinstance(item, dict) or not item.get("field") or not item.get("snippet"):
                    return "each field_evidence entry needs non-empty 'field' and 'snippet'"
        if completeness == "not inspectable" and not artifact.get("reason"):
            return "reason is required when completeness='not inspectable'"
        if final:
            if not completeness:
                return "the final chunk must carry completeness (and L)"
            if not level:
                return "the final chunk must carry L ('undetermined' when facts are insufficient)"
            if not artifact.get("source"):
                return "the final chunk must carry the absolute source path"
        return None

    def _load_source_content(self, artifact: dict) -> str | ToolResult:
        """Read the artifact text from its `source` file (whole-file artifacts)."""
        from deeplogic_cli.utils.config_loader import read_file_with_encoding_fallback

        source = artifact.get("source")
        if not source:
            return self._error("content_from_source requires an absolute `source` path")
        resolved = Path(source).resolve()
        if self._allowed_roots and not any(
            resolved == r or r in resolved.parents for r in self._allowed_roots
        ):
            return self._error(f"source is outside the allowed roots: {resolved}")
        if not resolved.is_file():
            return self._error(f"source file not found: {resolved}")
        text = read_file_with_encoding_fallback(resolved)
        if text is None:
            return self._error(f"source file unreadable: {resolved}")
        return text

    def _add_reference(self, reference: dict) -> ToolResult:
        missing = [k for k in ("name", "referenced_by", "relationship") if not reference.get(k)]
        if missing:
            return self._error(f"reference missing required fields: {missing}")
        self._references.append(
            ExtractedReference(
                name=reference["name"],
                referenced_by=reference["referenced_by"],
                relationship=reference["relationship"],
            )
        )
        return self._ok(
            f"stored reference: {reference['referenced_by']} -> {reference['name']}",
            references=len(self._references),
        )

    def _set_attribution(self, attribution: dict) -> ToolResult:
        status = attribution.get("status")
        if status not in ATTRIBUTION_STATUSES:
            return self._error(
                f"attribution status must be one of {ATTRIBUTION_STATUSES}, got {status!r}"
            )
        self._attribution = Attribution(status=status, note=attribution.get("note", ""))
        return self._ok(f"attribution set to {status}")

    def _list(self) -> ToolResult:
        artifacts = []
        for (a_type, name), state in sorted(self._streams.items()):
            artifacts.append(
                {
                    "type": a_type,
                    "name": name,
                    "chunks": f"{len(state.chunks)}/{state.total_chunks}",
                    "final": state.record is not None,
                    "completeness": state.record.completeness if state.record else None,
                    "L": state.record.L if state.record else None,
                }
            )
        return ToolResult(
            content=json.dumps(
                {
                    "artifacts": artifacts,
                    "rejected_artifacts": [
                        f"{a_type}/{name}" for a_type, name in sorted(self._rejected_chunks)
                    ],
                    "references": len(self._references),
                    "attribution": self._attribution.status if self._attribution else None,
                },
                ensure_ascii=False,
            ),
            success=True,
        )

    # ------------------------------------------------------------------
    # CLI-side finalization
    # ------------------------------------------------------------------

    def finalize(self) -> tuple[list[ExtractedArtifact], list[str]]:
        """Build validated artifacts; returns (artifacts, incomplete_keys).

        A key is incomplete when it was submitted but has no accepted final chunk.
        Incomplete keys are excluded from the result and reported to the CLI,
        which turns them into EXIT_FAILURE per the design (§5.3).

        Pre-registered deterministic candidates (design §5.5) that the agent
        never covered with an authoritative record are synthesized with
        ``extraction_method="deterministic"`` and ``L="undetermined"`` — never
        silently dropped.
        """
        artifacts: list[ExtractedArtifact] = []
        incomplete: list[str] = []
        for (a_type, name), state in sorted(self._streams.items()):
            if state.record is None:
                incomplete.append(f"{a_type}/{name}")
            else:
                artifacts.append(state.record)
        incomplete.extend(
            f"{a_type}/{name}"
            for a_type, name in self._rejected_chunks.keys() - self._streams.keys()
        )

        covered = {(a.type, a.name) for a in artifacts}
        for candidate in self._candidates:
            key = ("tool", candidate["name"])
            if key in covered:
                continue
            artifacts.append(
                ExtractedArtifact(
                    type="tool",
                    name=candidate["name"],
                    schema=candidate.get("schema") or {},
                    completeness="full original",
                    L="undetermined",
                    evidence=f"tool registry entry in {candidate.get('source', 'unknown')}",
                    source=candidate.get("source", ""),
                    reason="",
                    extraction_method="deterministic",
                )
            )
        return artifacts, sorted(incomplete)

    def register_candidates(self, candidates: list[dict]) -> None:
        """Pre-register deterministic tool candidates (design §5.5).

        Each candidate: ``{"name": str, "schema": dict, "source": str}``. The
        agent is still required to produce an authoritative record; uncovered
        candidates are synthesized in ``finalize()``.
        """
        self._candidates = list(candidates)

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def references(self) -> list[ExtractedReference]:
        return list(self._references)

    @property
    def attribution(self) -> Attribution | None:
        return self._attribution

    @property
    def resend_log(self) -> list[str]:
        return list(self._resend_log)

    @property
    def recovered_keys(self) -> list[str]:
        return [
            f"{a_type}/{name}"
            for a_type, name in sorted(self._recovered)
            if self._streams[(a_type, name)].record is not None
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ok(message: str, **extra) -> ToolResult:
        payload = {"success": True, "message": message, **extra}
        return ToolResult(content=json.dumps(payload, ensure_ascii=False), success=True)

    @staticmethod
    def _error(message: str) -> ToolResult:
        return ToolResult(
            content=json.dumps({"success": False, "error": message}, ensure_ascii=False),
            success=False,
            error=message,
        )
