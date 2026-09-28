"""Resumable state machine for the PaperSpine → FigMirror → assembly loop."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .adapters import host_message
from .assembly import assemble_figures
from .body_integration import validate_figure_body_contract
from .bridges import FigMirrorBridge, PaperSpineBridge, PublicationCycleBridge
from .contracts import (
    ContractError,
    load_integration_job,
    load_json,
    resolve_within,
    validate_review_decision,
    write_json_atomic,
)


STAGES = {
    "initialized",
    "awaiting_candidates",
    "awaiting_review",
    "figures_confirmed",
    "awaiting_paper_integration",
    "canonical_paper_ready",
    "target_profile_ready",
    "rebuttal_validated",
    "rebuttal_materials_ready",
    "destination_rebuild_ready",
    "awaiting_external_authorization",
    "complete",
    "blocked",
}
STATE_SCHEMA_VERSION = "1.2"
PUBLICATION_STAGES = {
    "canonical_paper_ready",
    "target_profile_ready",
    "rebuttal_validated",
    "rebuttal_materials_ready",
    "destination_rebuild_ready",
    "awaiting_external_authorization",
}
FINAL_READINESS_DIMENSIONS = {
    "scientific_content_ready",
    "visual_ready",
    "citation_verified",
    "metadata_ready",
    "artifact_portable",
}

PAPERSPINE_CONFIG_CHOICES = {
    "workflow": {"rewrite_existing", "build_from_materials"},
    "scene": {"journal", "conference", "report_review", "competition"},
    "tier": {"flash", "pro"},
    "output_language": {"en", "zh"},
    "word_output": {"none", "docx"},
    "translation_package": {"none", "zh"},
    "reference_mode": {"local_first", "specified_paths", "web"},
    "humanize_tier": {"none", "light", "medium", "heavy"},
    "detection_platform": {"cnki", "weipu", "general"},
    "ui_language": {"zh", "en"},
}

PAPERSPINE_CONFIG_DEFAULTS = {
    "tier": "flash",
    "output_language": "zh",
    "word_output": "docx",
    "translation_package": "none",
    "reference_mode": "local_first",
    "reference_paths": ["."],
    "citation_target_count": 20,
    "humanize_tier": "medium",
    "detection_platform": "general",
    "ui_language": "zh",
    "target_name": "",
    "materials_dir": "",
    "draft_path": "",
    "user_motivation": "",
    "official_urls": [],
    "special_requirements": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class IntegrationCoordinator:
    def __init__(self, job_path: str | Path) -> None:
        self.job = load_integration_job(job_path)
        self.state_path = Path(self.job["state_file"])
        self.paper = PaperSpineBridge(self.job)
        self.figmirror = FigMirrorBridge(self.job)
        self.publication = PublicationCycleBridge(self.job)

    def initialize(self, *, force: bool = False) -> dict[str, Any]:
        if self.state_path.exists() and not force:
            return self.state()
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "job_id": self.job["job_id"],
            "stage": "initialized",
            "next_action": "Validate the PaperSpine handoff and prepare FigMirror requests.",
            "events": [],
            "signals": [],
            "context": {},
            "updated_at": _now(),
        }
        self._event(state, "integration.initialized", {"host": self.job["host"]})
        return self._save(state)

    def state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return self.initialize()
        state = load_json(self.state_path)
        if state.get("job_id") != self.job["job_id"] or state.get("stage") not in STAGES:
            raise ContractError("integration_state.json does not match the configured job")
        if state.get("schema_version") == "1.0":
            previous_stage = state["stage"]
            state["schema_version"] = STATE_SCHEMA_VERSION
            if previous_stage == "complete":
                state["stage"] = "awaiting_paper_integration"
                state["next_action"] = (
                    "Consume figure_body_contract.json in the manuscript, finish the PaperSpine final pixel audit, then advance again."
                )
            self._event(
                state,
                "integration.state_migrated",
                {"from_schema": "1.0", "from_stage": previous_stage},
            )
            return self._save(state)
        if state.get("schema_version") == "1.1":
            previous_stage = state["stage"]
            state["schema_version"] = STATE_SCHEMA_VERSION
            if previous_stage == "complete":
                state["stage"] = "canonical_paper_ready"
                state["next_action"] = (
                    "Choose a Publication Cycle operation; canonical paper completion is not target-bundle readiness."
                )
            self._event(
                state,
                "integration.state_migrated",
                {"from_schema": "1.1", "from_stage": previous_stage},
            )
            return self._save(state)
        if state.get("schema_version") != STATE_SCHEMA_VERSION:
            raise ContractError(
                f"integration_state.json schema_version must be {STATE_SCHEMA_VERSION}"
            )
        return state

    @staticmethod
    def _generation_requests(requests: dict[str, Any]) -> dict[str, Any]:
        return {
            **requests,
            "figures": [
                figure for figure in requests["figures"] if figure.get("decision") != "keep"
            ],
        }

    def _save(self, state: dict[str, Any]) -> dict[str, Any]:
        state["updated_at"] = _now()
        write_json_atomic(self.state_path, state)
        return state

    @staticmethod
    def _event(state: dict[str, Any], event_type: str, payload: dict[str, Any] | None = None) -> None:
        state.setdefault("events", []).append(
            {"type": event_type, "at": _now(), "payload": payload or {}}
        )

    def _block(self, state: dict[str, Any], exc: Exception) -> dict[str, Any]:
        previous = state.get("stage")
        state["stage"] = "blocked"
        state["blocked_from"] = previous
        state["last_error"] = str(exc)
        state["next_action"] = "Resolve the recorded error, then run resume."
        self._event(state, "integration.blocked", {"from": previous, "error": str(exc)})
        return self._save(state)

    def resume(self) -> dict[str, Any]:
        state = self.state()
        if state["stage"] == "blocked":
            state["stage"] = state.get("blocked_from", "initialized")
            state.pop("last_error", None)
            state.pop("blocked_from", None)
            self._event(state, "integration.resumed")
            self._save(state)
        return self.advance()

    def advance(self) -> dict[str, Any]:
        state = self.state()
        if state["stage"] in PUBLICATION_STAGES:
            return state
        try:
            while True:
                if state["stage"] == "initialized":
                    requests, progress = self.paper.validate_handoff()
                    generation_requests = self._generation_requests(requests)
                    state["context"].update(
                        {
                            "paper_progress": progress,
                            "paper_id": requests["paper_id"],
                            "figure_count": len(requests["figures"]),
                            "generation_figure_count": len(generation_requests["figures"]),
                            "kept_figure_count": len(requests["figures"])
                            - len(generation_requests["figures"]),
                        }
                    )
                    if generation_requests["figures"]:
                        prepared = self.figmirror.prepare(generation_requests)
                        state["context"]["generation_plan"] = str(
                            self.figmirror.job_dir / "generation_plan.json"
                        )
                        state["stage"] = "awaiting_candidates"
                        state["next_action"] = (
                            "Use paperFig to author, render, inspect, and finalize every candidate declared in generation_plan.json."
                        )
                        self._event(
                            state,
                            "figmirror.plan_ready",
                            {
                                "figure_count": len(generation_requests["figures"]),
                                "kept_figure_count": state["context"]["kept_figure_count"],
                                "status": prepared["generation_plan"].get("status"),
                            },
                        )
                    else:
                        self.figmirror.write_auto_decision(requests, {"selected_candidates": {}})
                        state["stage"] = "figures_confirmed"
                        state["next_action"] = (
                            "Assemble the publication-ready figures retained by the PaperSpine story decision."
                        )
                        self._event(
                            state,
                            "figmirror.generation_not_applicable",
                            {"kept_figure_count": len(requests["figures"])},
                        )
                    self._save(state)
                    continue

                requests = self.paper.validate_handoff()[0]
                generation_requests = self._generation_requests(requests)
                if state["stage"] == "awaiting_candidates":
                    ready, missing = self.figmirror.candidates_ready(generation_requests)
                    if not ready:
                        state["context"]["missing_candidate_artifacts"] = missing
                        state["next_action"] = f"Waiting for {len(missing)} finalized candidate artifact(s)."
                        return self._save(state)
                    state["context"].pop("missing_candidate_artifacts", None)
                    results = self.figmirror.rank_and_build_review()
                    state["context"]["ranking"] = results["ranking"]
                    allow_auto = self.job["workflow"]["allow_auto_selection"]
                    if allow_auto and results["ranking"].get("decision") == "selected":
                        decision = self.figmirror.write_auto_decision(requests, results["ranking"])
                        validate_review_decision(decision, requests)
                        state["stage"] = "figures_confirmed"
                        state["next_action"] = "Assemble automatically selected figures."
                        self._event(state, "figmirror.auto_confirmed")
                    else:
                        state["stage"] = "awaiting_review"
                        state["next_action"] = "Open the unified UI and confirm one complete candidate per figure."
                        self._event(state, "figmirror.review_ready", {"index": results["review"].get("index")})
                    self._save(state)
                    continue

                if state["stage"] == "awaiting_review":
                    if not self.figmirror.decision_path.is_file():
                        return state
                    decision = validate_review_decision(load_json(self.figmirror.decision_path), requests)
                    if any(
                        panel.get("action") == "revise"
                        for item in decision["figures"]
                        for panel in item.get("panel_decisions", [])
                    ):
                        state["next_action"] = "At least one panel requests revision; update and re-finalize that candidate before confirming."
                        return self._save(state)
                    state["stage"] = "figures_confirmed"
                    state["next_action"] = "Assemble confirmed figures into the PaperSpine final-paper directory."
                    self._event(state, "figmirror.human_confirmed")
                    self._save(state)
                    continue

                if state["stage"] == "figures_confirmed":
                    decision = validate_review_decision(load_json(self.figmirror.decision_path), requests)
                    assembly = assemble_figures(self.job, requests, decision)
                    state["context"]["assembly_manifest"] = assembly["manifest"]
                    state["context"]["assembly_report"] = assembly["report"]
                    state["context"]["body_contract"] = assembly["body_contract"]
                    state["context"]["figure_asset_map"] = assembly["figure_asset_map"]
                    state["stage"] = "awaiting_paper_integration"
                    state["next_action"] = (
                        "Consume figure_body_contract.json in Results/captions with real body references, then complete PaperSpine LaTeX/Word and final pixel audit."
                    )
                    self._event(
                        state,
                        "integration.figure_assets_ready",
                        {"figures": len(assembly["figures"])},
                    )
                    self._save(state)
                    continue

                if state["stage"] == "awaiting_paper_integration":
                    self.body_contract()
                    progress = self.paper.progress_snapshot()
                    state["context"]["paper_progress"] = progress
                    readiness = progress.get("readiness") or {}
                    readiness_complete = FINAL_READINESS_DIMENSIONS.issubset(readiness) and all(
                        readiness.get(name) is True for name in FINAL_READINESS_DIMENSIONS
                    )
                    if progress.get("is_complete") is True and readiness_complete:
                        state["stage"] = "canonical_paper_ready"
                        state["next_action"] = (
                            "The canonical paper is complete. Validate a target profile, assemble a target bundle, prepare rebuttal materials, or plan a destination rebuild."
                        )
                        self._event(
                            state,
                            "paperspine.final_audit_confirmed",
                            {"readiness": readiness},
                        )
                        return self._save(state)
                    state["next_action"] = progress.get("next_action") or (
                        "Continue PaperSpine from its first incomplete stage, then advance this integration again."
                    )
                    return self._save(state)

                if state["stage"] == "blocked":
                    return state
                raise ContractError(f"unsupported integration stage: {state['stage']}")
        except Exception as exc:
            return self._block(state, exc)

    def record_decision(self, raw: dict[str, Any]) -> dict[str, Any]:
        state = self.state()
        if state["stage"] in PUBLICATION_STAGES:
            return state
        if state["stage"] != "awaiting_review":
            raise ContractError("a review decision is only accepted during awaiting_review")
        requests = self.paper.validate_handoff()[0]
        decision = validate_review_decision(raw, requests)
        request_by_id = {item["figure_id"]: item for item in requests["figures"]}
        generated_candidates = set("ABC"[: int(self.job["figure"]["candidate_count"])])
        invalid = [
            item["selected_candidate"]
            for item in decision["figures"]
            if item["selected_candidate"]
            not in (
                {"existing"}
                if request_by_id[item["figure_id"]].get("decision") == "keep"
                else generated_candidates
            )
        ]
        if invalid:
            raise ContractError(f"review selected a candidate outside this job: {invalid}")
        write_json_atomic(self.figmirror.decision_path, decision)
        self._event(state, "figmirror.decision_recorded", {"figures": len(decision["figures"])})
        self._save(state)
        return self.advance()

    def configuration(self) -> dict[str, Any]:
        output = Path(self.job["paper"]["output_dir"])
        config_path = output / "paper_spine_config.json"
        values = load_json(config_path) if config_path.is_file() else None
        if values is not None and not isinstance(values, dict):
            values = None
        return {
            "exists": values is not None,
            "values": values,
            "output_dir": str(output),
            "config_file": str(config_path),
            "entry_command": "/paperspine",
        }

    @staticmethod
    def _normalize_configuration(raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ContractError("PaperSpine configuration must be a JSON object")
        normalized = {**PAPERSPINE_CONFIG_DEFAULTS, **raw}
        for field, allowed in PAPERSPINE_CONFIG_CHOICES.items():
            value = normalized.get(field)
            if value not in allowed:
                raise ContractError(f"configuration.{field} is unsupported")
        if not normalized.get("workflow") or not normalized.get("scene"):
            raise ContractError("configuration requires workflow and scene")
        for field in ("target_name", "materials_dir", "draft_path", "user_motivation"):
            value = normalized.get(field)
            if not isinstance(value, str):
                raise ContractError(f"configuration.{field} must be text")
            normalized[field] = value.strip()
        if not normalized["target_name"]:
            raise ContractError("configuration.target_name is required")
        for field in ("official_urls", "reference_paths", "special_requirements"):
            value = normalized.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ContractError(f"configuration.{field} must be a text list")
            normalized[field] = [item.strip() for item in value if item.strip()]
        if not normalized["reference_paths"]:
            normalized["reference_paths"] = ["."]
        citation_count = normalized.get("citation_target_count")
        if isinstance(citation_count, bool) or not isinstance(citation_count, int) or not 1 <= citation_count <= 500:
            raise ContractError("configuration.citation_target_count must be an integer from 1 to 500")
        return normalized

    @staticmethod
    def _configuration_markdown(config: dict[str, Any]) -> str:
        labels = {
            "workflow": "工作流",
            "scene": "目标场景",
            "tier": "调研深度",
            "output_language": "最终输出语言",
            "target_name": "目标名称",
            "materials_dir": "素材文件夹",
            "draft_path": "初稿路径",
            "user_motivation": "初始动机假设",
            "official_urls": "官方链接",
            "reference_mode": "文献读取模式",
            "reference_paths": "本地参考路径",
            "citation_target_count": "引用目标数",
            "special_requirements": "特殊要求",
            "word_output": "Word 输出",
            "translation_package": "翻译包",
            "humanize_tier": "降 AI 痕迹",
            "detection_platform": "目标检测平台",
            "ui_language": "界面语言",
        }
        lines = ["# PaperSpine 配置", ""]
        for field, label in labels.items():
            value = config.get(field)
            rendered = "；".join(value) if isinstance(value, list) else str(value or "")
            lines.append(f"- **{label}**：{rendered}")
        return "\n".join(lines) + "\n"

    def save_configuration(self, raw: dict[str, Any]) -> dict[str, Any]:
        state = self.state()
        editable_stage = state.get("blocked_from") if state["stage"] == "blocked" else state["stage"]
        if editable_stage != "initialized":
            raise ContractError("PaperSpine configuration can only change before the integration advances")
        config = self._normalize_configuration(raw)
        output = Path(self.job["paper"]["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        write_json_atomic(output / "paper_spine_config.json", config)
        (output / "paper_spine_config.md").write_text(
            self._configuration_markdown(config), encoding="utf-8"
        )
        self._event(state, "paperspine.configuration.saved", {"target_name": config["target_name"]})
        self._save(state)
        return {"status": "OK", "configuration": self.configuration(), "state": state}

    def deliverables(self, paper_progress: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.state()
        final_dir = Path(self.job["assembly"]["final_paper_dir"])
        files: list[dict[str, Any]] = []
        if final_dir.is_dir():
            for path in sorted(item for item in final_dir.rglob("*") if item.is_file())[:200]:
                files.append(
                    {
                        "path": path.relative_to(final_dir).as_posix(),
                        "size": path.stat().st_size,
                    }
                )
        publication = state.get("context", {}).get("publication_cycle") or {}
        latest_result = (publication.get("latest") or {}).get("result") or {}
        latest_signals = latest_result.get("signals") or {}
        canonical_ready = bool(
            (state["stage"] in PUBLICATION_STAGES or state.get("blocked_from") in PUBLICATION_STAGES)
            and final_dir.is_dir()
            and paper_progress
            and paper_progress.get("is_complete") is True
        )
        bundle_ready = bool(
            latest_result.get("ok") is True
            and latest_signals.get("submission_bundle_ready") is True
            and (
                state["stage"] == "awaiting_external_authorization"
                or state.get("blocked_from") == "awaiting_external_authorization"
            )
        )
        return {
            "ready": bundle_ready,
            "canonical_ready": canonical_ready,
            "bundle_ready": bundle_ready,
            "directory": str(final_dir),
            "files": files,
            "manifest": state.get("context", {}).get("assembly_manifest"),
            "report": state.get("context", {}).get("assembly_report"),
            "body_contract": state.get("context", {}).get("body_contract"),
            "figure_asset_map": state.get("context", {}).get("figure_asset_map"),
            "paper_complete": bool(paper_progress and paper_progress.get("is_complete") is True),
            "paper_next_stage": (paper_progress or {}).get("next_stage"),
            "paper_next_action": (paper_progress or {}).get("next_action"),
        }

    @staticmethod
    def _canonical_readiness(progress: dict[str, Any] | None) -> bool:
        readiness = (progress or {}).get("readiness") or {}
        return bool(
            (progress or {}).get("is_complete") is True
            and FINAL_READINESS_DIMENSIONS.issubset(readiness)
            and all(readiness.get(name) is True for name in FINAL_READINESS_DIMENSIONS)
        )

    def publication_cycle_snapshot(self) -> dict[str, Any]:
        state = self.state()
        enabled = self.job["publication"]["enabled"]
        effective_stage = state.get("blocked_from") if state["stage"] == "blocked" else state["stage"]
        context = state.get("context", {}).get("publication_cycle") or {}
        descriptor = self.publication.describe() if enabled else None
        return {
            "enabled": enabled,
            "interface": descriptor,
            "stage": effective_stage,
            "allowed_operations": (
                [item["id"] for item in descriptor.get("operations", [])]
                if descriptor and effective_stage in PUBLICATION_STAGES
                else []
            ),
            "latest": context.get("latest"),
            "history": context.get("history", []),
            "canonical_paper_ready": effective_stage in PUBLICATION_STAGES,
            "submission_bundle_ready": bool(
                ((context.get("latest") or {}).get("result") or {})
                .get("signals", {})
                .get("submission_bundle_ready")
            ),
            "external_action_authorized": False,
            "authority_note": (
                "Publication Cycle only validates and builds local artifacts. External submission, resubmission, fees, and licenses always require separate user authorization."
            ),
        }

    def invoke_publication_cycle(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not self.job["publication"]["enabled"]:
            raise ContractError("Publication Cycle is disabled for this integration job")
        state = self.state()
        base_stage = state.get("blocked_from") if state["stage"] == "blocked" else state["stage"]
        if base_stage not in PUBLICATION_STAGES:
            raise ContractError("Publication Cycle is available only after canonical_paper_ready")
        progress = state.get("context", {}).get("paper_progress")
        if not self._canonical_readiness(progress):
            raise ContractError("the canonical paper and all five PaperSpine readiness dimensions must be complete")

        descriptor = self.publication.describe()
        operation = raw.get("operation")
        operation_spec = next(
            (item for item in descriptor["operations"] if item.get("id") == operation),
            None,
        )
        if operation_spec is None:
            raise ContractError("publication operation is unsupported")
        raw_inputs = raw.get("inputs", {})
        raw_outputs = raw.get("outputs", {})
        raw_options = raw.get("options", {})
        if not isinstance(raw_inputs, dict) or not isinstance(raw_outputs, dict) or not isinstance(raw_options, dict):
            raise ContractError("publication inputs, outputs, and options must be JSON objects")

        invocation_root = self.publication.invocation_dir.resolve()
        invocation_root.mkdir(parents=True, exist_ok=True)
        invocation_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        request_path = invocation_root / f"{invocation_id}-{operation}.request.json"
        project_root = Path(self.job["project_root"]).resolve()

        def invocation_relative(value: Any, field: str) -> str:
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{field} must be a non-empty project-root-relative or absolute path")
            resolved = resolve_within(project_root, value.strip(), field)
            return os.path.relpath(resolved, invocation_root)

        inputs: dict[str, str] = {}
        for name in operation_spec.get("required_inputs", []):
            if name in raw_inputs:
                inputs[name] = invocation_relative(raw_inputs[name], f"publication.inputs.{name}")

        outputs: dict[str, str] = {}
        if "directory" in operation_spec.get("required_outputs", []):
            output_value = raw_outputs.get("directory")
            if not output_value:
                output_value = str(
                    Path(self.job["paper"]["output_dir"])
                    / "publication_cycle"
                    / "outputs"
                    / f"{operation}-{invocation_id}"
                )
            outputs["directory"] = invocation_relative(
                output_value, "publication.outputs.directory"
            )

        request = {
            "contract": "paperspine.publication-cycle.invoke-request",
            "interface_version": "1.0",
            "operation": operation,
            "project_root": os.path.relpath(project_root, invocation_root),
            "inputs": inputs,
            **({"outputs": outputs} if outputs else {}),
            "options": {"write_report": raw_options.get("write_report") is True},
        }
        write_json_atomic(request_path, request)
        result = self.publication.invoke(request_path)
        result_path = request_path.with_suffix("").with_suffix(".result.json")
        write_json_atomic(result_path, result)
        record = {
            "invocation_id": invocation_id,
            "operation": operation,
            "request": str(request_path),
            "result_file": str(result_path),
            "result": result,
            "recorded_at": _now(),
        }
        publication_context = state.setdefault("context", {}).setdefault(
            "publication_cycle", {"history": []}
        )
        publication_context.setdefault("history", []).append(record)
        publication_context["latest"] = record

        if result.get("ok") is not True or result.get("stage") == "blocked":
            findings = result.get("blocking_findings") or [result.get("outcome", "BLOCKED")]
            state["stage"] = "blocked"
            state["blocked_from"] = base_stage
            state["last_error"] = "; ".join(str(item) for item in findings)
            next_action = result.get("next_action") or {}
            state["next_action"] = next_action.get("action") or "Resolve the Publication Cycle findings, then invoke the operation again."
            self._event(
                state,
                "publication_cycle.blocked",
                {"operation": operation, "findings": findings},
            )
            return self._save(state)

        stage_map = {
            "target_profile_ready": "target_profile_ready",
            "target_bundle_ready": "awaiting_external_authorization",
            "rebuttal_validated": "rebuttal_validated",
            "rebuttal_materials_ready": "rebuttal_materials_ready",
            "destination_rebuild_ready": "destination_rebuild_ready",
        }
        result_stage = result.get("stage")
        if result_stage not in stage_map:
            raise ContractError(f"publication-cycle returned unsupported success stage: {result_stage}")
        state["stage"] = stage_map[result_stage]
        state.pop("blocked_from", None)
        state.pop("last_error", None)
        next_action = result.get("next_action") or {}
        state["next_action"] = next_action.get("action") or "Inspect the local Publication Cycle artifacts."
        self._event(
            state,
            "publication_cycle.operation_complete",
            {"operation": operation, "result_stage": result_stage, "result_file": str(result_path)},
        )
        return self._save(state)

    def body_contract(self, *, required: bool = True) -> dict[str, Any] | None:
        path = Path(self.job["paper"]["output_dir"]) / "figure_body_contract.json"
        if not path.is_file():
            if required:
                raise ContractError("figure_body_contract.json is not available until confirmed figures are assembled")
            return None
        requests = self.paper.validate_handoff()[0]
        return validate_figure_body_contract(
            load_json(path), requests=requests, output_dir=Path(self.job["paper"]["output_dir"])
        )

    def record_signal(self, raw: dict[str, Any]) -> dict[str, Any]:
        state = self.state()
        if raw.get("schema_version") != "1.0" or raw.get("job_id") != self.job["job_id"]:
            raise ContractError("signal does not match this integration job")
        signal_type = raw.get("signal_type")
        if signal_type not in {"continue", "motivation_confirmed", "contribution_confirmed", "figure_review_confirmed"}:
            raise ContractError("unsupported integration signal_type")
        if raw.get("source") not in {"codex", "claude-code", "dsh", "standalone-skill", "ui", "user"}:
            raise ContractError("signal source is unsupported")
        state.setdefault("signals", []).append({**raw, "recorded_at": _now()})
        self._event(state, "integration.signal", {"signal_type": signal_type, "source": raw.get("source")})
        self._save(state)
        return self.advance() if signal_type == "continue" else state

    def host_next(self, host: str | None = None) -> dict[str, Any]:
        return host_message(self.job, self.state(), host)

    def workflow_snapshot(
        self,
        *,
        state: dict[str, Any] | None = None,
        requests: dict[str, Any] | None = None,
        paper_progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = state or self.state()
        if requests is None and self.paper.request_path.is_file():
            requests = self.paper.validate_handoff()[0]
        if paper_progress is None:
            try:
                paper_progress = self.paper.progress_snapshot()
            except Exception:
                paper_progress = None
        figures = (requests or {}).get("figures", [])
        generated = [item for item in figures if item.get("decision") != "keep"]
        stage = state["stage"]
        effective_stage = state.get("blocked_from") if stage == "blocked" else stage
        publication_context = state.get("context", {}).get("publication_cycle") or {}
        latest_publication = (publication_context.get("latest") or {}).get("result") or {}
        post_paper = effective_stage in PUBLICATION_STAGES
        after_candidates = stage in {
            "awaiting_review",
            "figures_confirmed",
            "awaiting_paper_integration",
            "complete",
        } or post_paper
        after_review = stage in {"figures_confirmed", "awaiting_paper_integration", "complete"} or post_paper
        body_path = Path(self.job["paper"]["output_dir"]) / "figure_body_contract.json"
        body_ready = body_path.is_file()
        referenced_labels: list[str] = []
        if body_ready:
            try:
                contract = self.body_contract()
                tex_path = Path(self.job["assembly"]["main_tex"])
                tex = tex_path.read_text(encoding="utf-8") if tex_path.is_file() else ""
                tex_references = {
                    label.strip()
                    for match in re.finditer(r"\\(?:ref|autoref|cref)\{([^}]*)\}", tex)
                    for label in match.group(1).split(",")
                    if label.strip()
                }
                for figure in contract["figures"]:
                    if figure["label"] in tex_references:
                        referenced_labels.append(figure["label"])
            except Exception:
                body_ready = False
        all_labels_referenced = bool(figures) and len(referenced_labels) == len(figures)
        readiness = (paper_progress or {}).get("readiness") or {}
        phases = [
            {
                "phase": "figure_understanding_and_story",
                "status": "complete" if figures else "pending",
                "evidence": self.paper.request_path.as_posix(),
            },
            {
                "phase": "candidate_authoring_and_qa",
                "status": "not_applicable" if not generated else "complete" if after_candidates else "active" if stage == "awaiting_candidates" else "pending",
                "evidence": state.get("context", {}).get("generation_plan"),
            },
            {
                "phase": "whole_figure_review",
                "status": "complete" if after_review else "active" if stage == "awaiting_review" else "pending",
                "evidence": str(self.figmirror.decision_path),
            },
            {
                "phase": "assembly_and_body_contract",
                "status": "complete" if body_ready else "pending",
                "evidence": str(body_path),
            },
            {
                "phase": "manuscript_reference_integration",
                "status": "complete" if all_labels_referenced else "active" if body_ready else "pending",
                "evidence": str(self.job["assembly"]["main_tex"]),
                "referenced_labels": referenced_labels,
            },
            {
                "phase": "final_pixel_and_paper_audit",
                "status": "complete" if readiness.get("visual_ready") is True and (paper_progress or {}).get("is_complete") is True else "active" if body_ready else "pending",
                "evidence": str(Path(self.job["paper"]["output_dir"]) / "visual_audit_manifest.json"),
                "readiness": readiness,
            },
            {
                "phase": "canonical_paper_ready",
                "status": "complete" if post_paper else "pending",
                "evidence": "integration_state.json#context.paper_progress",
            },
            {
                "phase": "publication_cycle",
                "status": (
                    "target_bundle_ready"
                    if latest_publication.get("signals", {}).get("submission_bundle_ready") is True
                    else "complete"
                    if latest_publication.get("ok") is True
                    else "active"
                    if post_paper
                    else "pending"
                ),
                "evidence": (publication_context.get("latest") or {}).get("result_file"),
                "operation": latest_publication.get("operation"),
                "external_action_authorized": False,
            },
        ]
        return {
            "schema_version": "1.1",
            "job_id": self.job["job_id"],
            "status": (
                "blocked"
                if stage == "blocked"
                else "ready_for_external_authorization"
                if stage == "awaiting_external_authorization"
                else "canonical_paper_ready"
                if stage == "canonical_paper_ready"
                else "in_progress"
            ),
            "stage": stage,
            "figure_counts": {
                "total": len(figures),
                "keep": len(figures) - len(generated),
                "generate_or_redesign": len(generated),
            },
            "phases": phases,
            "next_action": state.get("next_action"),
        }

    def snapshot(self) -> dict[str, Any]:
        requests: dict[str, Any] | None = None
        contribution = None
        motivation = None
        paper_progress: dict[str, Any] | None = None
        if self.paper.request_path.is_file():
            requests = self.paper.validate_handoff()[0]
        output = Path(self.job["paper"]["output_dir"])
        if output.is_dir():
            try:
                paper_progress = self.paper.progress_snapshot()
            except Exception:
                paper_progress = None
        for name, key in (("confirmed_contribution.md", "contribution"), ("confirmed_motivation.md", "motivation")):
            path = output / name
            value = path.read_text(encoding="utf-8-sig") if path.is_file() else None
            if key == "contribution":
                contribution = value
            else:
                motivation = value
        state = self.state()
        return {
            "job": {"job_id": self.job["job_id"], "host": self.job["host"]},
            "state": state,
            "paper": {
                "contribution": contribution,
                "motivation": motivation,
                "requests": requests,
                "progress": paper_progress,
            },
            "review": self.figmirror.review_data(),
            "host_next": self.host_next(),
            "configuration": self.configuration(),
            "deliverables": self.deliverables(paper_progress),
            "publication_cycle": self.publication_cycle_snapshot(),
            "body_contract": self.body_contract(required=False),
            "workflow": self.workflow_snapshot(
                state=state,
                requests=requests,
                paper_progress=paper_progress,
            ),
        }
