"""Controlled canonical-manuscript editing, rebuild, and receipt evidence.

This module deliberately edits the declared manuscript source, never a binary
PDF.  PDF and Word files are rebuild products and every change is backed up
before the canonical source is replaced.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ContractError, resolve_within, write_json_atomic


SECTION_RE = re.compile(r"(?m)^\\(section\*?)\{([^{}]*)\}\s*")
BEGIN_DOCUMENT_RE = re.compile(r"\\begin\{document\}")
END_DOCUMENT_RE = re.compile(r"\\end\{document\}")
SAFE_SECTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

class ManuscriptBuildError(RuntimeError):
    """Raised when a declared rebuild product cannot be produced."""

    def __init__(
        self,
        message: str,
        *,
        missing_tools: list[str] | None = None,
        failed_candidate_file: str | None = None,
        backup_directory: str | None = None,
    ) -> None:
        super().__init__(message)
        self.missing_tools = missing_tools or []
        self.failed_candidate_file = failed_candidate_file
        self.backup_directory = backup_directory


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _page_count(pdf_path: Path) -> int:
    if not pdf_path.is_file():
        return 0
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        # A conservative fallback for environments where pypdf is unavailable.
        data = pdf_path.read_bytes()
        return len(re.findall(rb"/Type\s*/Page\b", data))


def _clean_tex_title(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be non-empty text")
    title = value.strip()
    if len(title) > 500 or any(char in title for char in "{}\r\n"):
        raise ContractError(f"{field} contains unsupported TeX title characters")
    return title


class ManuscriptRevisionService:
    """Operate on one job's declared source and generated manuscript products."""

    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job
        self.project_root = Path(job["project_root"]).resolve()
        settings = job["manuscript"]
        self.source_path = Path(settings["source_file"])
        self.pdf_path = Path(settings["pdf_file"])
        self.word_path = Path(settings["word_file"])
        self.revision_root = Path(settings["revision_dir"])
        self.pdf_engine = settings["pdf_engine"]
        self.word_engine = settings["word_engine"]
        self.require_pdf = settings["require_pdf"]
        self.require_word = settings["require_word"]
        self.receipt_groups = settings["receipt_groups"]

    def _assert_declared_paths(self) -> None:
        for field, path in (
            ("manuscript.source_file", self.source_path),
            ("manuscript.pdf_file", self.pdf_path),
            ("manuscript.word_file", self.word_path),
            ("manuscript.revision_dir", self.revision_root),
        ):
            resolve_within(self.project_root, path, field)

    def parse_source(self) -> dict[str, Any]:
        self._assert_declared_paths()
        if not self.source_path.is_file():
            raise ContractError(f"canonical manuscript source does not exist: {self.source_path}")
        source = self.source_path.read_text(encoding="utf-8-sig")
        begin = BEGIN_DOCUMENT_RE.search(source)
        end_matches = list(END_DOCUMENT_RE.finditer(source))
        if begin is None or not end_matches or end_matches[-1].start() <= begin.end():
            raise ContractError("canonical manuscript must contain one complete document environment")
        content_start = begin.end()
        content_end = end_matches[-1].start()
        body = source[content_start:content_end]
        matches = list(SECTION_RE.finditer(body))
        if not matches:
            sections = [{"section_id": "section-1", "title": "正文", "body": body.strip()}]
            front_matter = ""
        else:
            front_matter = body[: matches[0].start()].strip()
            sections = []
            for index, match in enumerate(matches):
                stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
                sections.append(
                    {
                        "section_id": f"section-{index + 1}",
                        "title": match.group(2).strip(),
                        "body": body[match.end() : stop].strip(),
                        "starred": match.group(1).endswith("*"),
                    }
                )
        return {
            "source": source,
            "preamble": source[:content_start],
            "ending": source[content_end:],
            "front_matter": front_matter,
            "sections": sections,
        }

    def hashes(self) -> dict[str, str | None]:
        return {
            "source_sha256": _sha256(self.source_path),
            "pdf_sha256": _sha256(self.pdf_path),
            "word_sha256": _sha256(self.word_path),
        }

    def artifact_snapshot(self) -> dict[str, Any]:
        parsed = self.parse_source()
        return {
            "editing_contract": "canonical-source-sections; PDF is preview-only",
            "source_file": str(self.source_path),
            "pdf_file": str(self.pdf_path),
            "word_file": str(self.word_path),
            "front_matter": parsed["front_matter"],
            "sections": parsed["sections"],
            "page_count": _page_count(self.pdf_path),
            "hashes": self.hashes(),
            "products": {
                "pdf": {"required": self.require_pdf, "exists": self.pdf_path.is_file()},
                "word": {"required": self.require_word, "exists": self.word_path.is_file()},
            },
        }

    def _validate_edit(self, raw: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        front_matter = raw.get("front_matter", "")
        if not isinstance(front_matter, str) or len(front_matter) > 250_000:
            raise ContractError("manuscript.front_matter must be text no longer than 250000 characters")
        raw_sections = raw.get("sections")
        if not isinstance(raw_sections, list) or not 1 <= len(raw_sections) <= 100:
            raise ContractError("manuscript.sections must contain from 1 to 100 sections")
        sections: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, value in enumerate(raw_sections):
            if not isinstance(value, dict):
                raise ContractError(f"manuscript.sections[{index}] must be an object")
            section_id = value.get("section_id")
            if not isinstance(section_id, str) or not SAFE_SECTION_ID.fullmatch(section_id) or section_id in seen:
                raise ContractError("manuscript section IDs must be unique safe identifiers")
            seen.add(section_id)
            body = value.get("body")
            if not isinstance(body, str) or len(body) > 2_000_000:
                raise ContractError(f"manuscript.sections[{index}].body must be text")
            starred = value.get("starred", False)
            if not isinstance(starred, bool):
                raise ContractError(f"manuscript.sections[{index}].starred must be boolean")
            sections.append(
                {
                    "section_id": section_id,
                    "title": _clean_tex_title(value.get("title"), f"manuscript.sections[{index}].title"),
                    "body": body.strip(),
                    "starred": starred,
                }
            )
        return front_matter.strip(), sections

    def _render(self, parsed: dict[str, Any], front_matter: str, sections: list[dict[str, Any]]) -> str:
        chunks = [parsed["preamble"].rstrip(), ""]
        if front_matter:
            chunks.extend([front_matter, ""])
        for section in sections:
            command = "section*" if section["starred"] else "section"
            chunks.append(f"\\{command}{{{section['title']}}}")
            if section["body"]:
                chunks.append(section["body"])
            chunks.append("")
        chunks.append(parsed["ending"].lstrip())
        return "\n".join(chunks).rstrip() + "\n"

    def _backup(self, revision_id: str, paths: list[Path]) -> Path:
        backup = self.revision_root / revision_id / "before"
        backup.mkdir(parents=True, exist_ok=False)
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(self.project_root)
            destination = backup / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        return backup

    def _restore_backup(self, backup: Path, paths: list[Path], before_hashes: dict[str, Any]) -> None:
        hash_keys = {
            self.source_path.resolve(): "source_sha256",
            self.pdf_path.resolve(): "pdf_sha256",
            self.word_path.resolve(): "word_sha256",
        }
        for path in paths:
            relative = path.relative_to(self.project_root)
            saved = backup / relative
            if saved.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved, path)
                continue
            key = hash_keys.get(path.resolve())
            if key and before_hashes.get(key) is None and path.is_file():
                path.unlink()

    @staticmethod
    def _promote_file(candidate: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.promote.tmp")
        shutil.copy2(candidate, temporary)
        temporary.replace(destination)

    @staticmethod
    def _run(command: list[str], cwd: Path) -> None:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise ManuscriptBuildError(f"manuscript rebuild failed: {detail}")

    def _pdf_command(self, output_dir: Path) -> tuple[list[str], Path]:
        configured = None if self.pdf_engine == "auto" else self.pdf_engine
        candidates = [configured] if configured else ["latexmk", "xelatex", "pdflatex", "tectonic"]
        engine = next((name for name in candidates if name and shutil.which(name)), None)
        if engine is None:
            raise ManuscriptBuildError(
                "no supported LaTeX engine is available for the required PDF rebuild",
                missing_tools=[name for name in candidates if name],
            )
        if engine == "latexmk":
            command = [
                engine,
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-outdir={output_dir}",
                self.source_path.name,
            ]
        elif engine == "tectonic":
            command = [
                engine,
                "--keep-logs",
                "--keep-intermediates",
                "--outdir",
                str(output_dir),
                self.source_path.name,
            ]
        else:
            command = [
                engine,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={output_dir}",
                self.source_path.name,
            ]
        return command, output_dir / self.source_path.with_suffix(".pdf").name

    def _build_pdf(self, output_dir: Path) -> tuple[dict[str, Any], Path]:
        command, generated = self._pdf_command(output_dir)
        self._run(command, self.source_path.parent)
        if not generated.is_file():
            raise ManuscriptBuildError(f"PDF engine completed without creating {generated.name}")
        return {"command": command, "output": str(self.pdf_path), "candidate": str(generated)}, generated

    def _build_word(self, output_dir: Path) -> tuple[dict[str, Any], Path]:
        engine = "pandoc" if self.word_engine == "auto" else self.word_engine
        if not shutil.which(engine):
            raise ManuscriptBuildError(
                "pandoc is not available for the required Word rebuild", missing_tools=[engine]
            )
        candidate = output_dir / self.word_path.name
        command = [
            engine,
            self.source_path.name,
            "-o",
            str(candidate),
            "--from",
            "latex",
            "--to",
            "docx",
            f"--resource-path={self.source_path.parent}",
            "--number-sections",
        ]
        bibliography = self.source_path.parent / "references.bib"
        if bibliography.is_file():
            command.extend(["--citeproc", f"--bibliography={bibliography}"])
        output_dir.mkdir(parents=True, exist_ok=True)
        self._run(command, self.source_path.parent)
        if not candidate.is_file():
            raise ManuscriptBuildError("pandoc completed without creating the declared Word output")
        return {"command": command, "output": str(self.word_path), "candidate": str(candidate)}, candidate

    def rebuild(self, revision_id: str, before_hashes: dict[str, Any]) -> dict[str, Any]:
        build: dict[str, Any] = {"pdf": None, "word": None}
        candidate_build = self.revision_root / revision_id / "candidate-build"
        candidate_build.mkdir(parents=True, exist_ok=True)
        pdf_candidate: Path | None = None
        word_candidate: Path | None = None
        if self.require_pdf:
            build["pdf"], pdf_candidate = self._build_pdf(candidate_build)
        if self.require_word:
            build["word"], word_candidate = self._build_word(candidate_build)
        # Generated products are promoted only after every required build has
        # succeeded, so a partial build cannot overwrite last-known-good files.
        if pdf_candidate is not None:
            self._promote_file(pdf_candidate, self.pdf_path)
        if word_candidate is not None:
            self._promote_file(word_candidate, self.word_path)
        after_hashes = self.hashes()
        if self.require_pdf and not after_hashes["pdf_sha256"]:
            raise ManuscriptBuildError("required PDF output is missing after rebuild")
        if self.require_word and not after_hashes["word_sha256"]:
            raise ManuscriptBuildError("required Word output is missing after rebuild")
        receipt = {
            "contract": "paperspine5.manuscript-rebuild",
            "version": "1.0",
            "revision_id": revision_id,
            "rebuilt_at": _now(),
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "build": build,
        }
        receipt_path = self.revision_root / revision_id / "rebuild-receipt.json"
        write_json_atomic(receipt_path, receipt)
        return {**receipt, "receipt_file": str(receipt_path)}

    def apply_revision(self, raw: dict[str, Any], revision_id: str) -> dict[str, Any]:
        parsed = self.parse_source()
        expected = raw.get("base_source_sha256")
        current = _sha256(self.source_path)
        if not isinstance(expected, str) or expected != current:
            raise ContractError("base_source_sha256 does not match the current canonical source")
        front_matter, sections = self._validate_edit(raw)
        before_hashes = self.hashes()
        backup = self._backup(revision_id, [self.source_path, self.pdf_path, self.word_path])
        candidate_file = self.revision_root / revision_id / "candidate" / self.source_path.name
        candidate_text = self._render(parsed, front_matter, sections)
        _atomic_text(candidate_file, candidate_text)
        _atomic_text(self.source_path, candidate_text)
        try:
            rebuild = self.rebuild(revision_id, before_hashes)
        except Exception as exc:
            self._restore_backup(
                backup,
                [self.source_path, self.pdf_path, self.word_path],
                before_hashes,
            )
            failure = {
                "contract": "paperspine5.manuscript-rebuild",
                "version": "1.0",
                "revision_id": revision_id,
                "status": "BLOCKED",
                "failed_at": _now(),
                "before_hashes": before_hashes,
                "current_hashes": self.hashes(),
                "backup_directory": str(backup),
                "failed_candidate_file": str(candidate_file),
                "canonical_restored": self.hashes() == before_hashes,
            }
            write_json_atomic(self.revision_root / revision_id / "rebuild-failure.json", failure)
            if isinstance(exc, ManuscriptBuildError):
                exc.failed_candidate_file = str(candidate_file)
                exc.backup_directory = str(backup)
                raise
            raise ManuscriptBuildError(
                str(exc),
                failed_candidate_file=str(candidate_file),
                backup_directory=str(backup),
            ) from exc
        return {
            "revision_id": revision_id,
            "backup_directory": str(backup),
            "before_hashes": before_hashes,
            "after_hashes": rebuild["after_hashes"],
            "rebuild_receipt": rebuild["receipt_file"],
        }

    def retry_failed_revision(
        self,
        revision_id: str,
        failed_candidate_file: str,
        before_hashes: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = resolve_within(
            self.project_root,
            failed_candidate_file,
            "manuscript.failed_candidate_file",
            must_exist=True,
        )
        revision_directory = (self.revision_root / revision_id).resolve()
        try:
            candidate.relative_to(revision_directory)
        except ValueError as exc:
            raise ContractError("failed manuscript candidate is outside its revision directory") from exc
        backup = revision_directory / "before"
        _atomic_text(self.source_path, candidate.read_text(encoding="utf-8-sig"))
        try:
            rebuild = self.rebuild(revision_id, before_hashes)
        except Exception:
            self._restore_backup(
                backup,
                [self.source_path, self.pdf_path, self.word_path],
                before_hashes,
            )
            raise
        return {
            "revision_id": revision_id,
            "failed_candidate_file": str(candidate),
            "backup_directory": str(backup),
            "before_hashes": before_hashes,
            "after_hashes": rebuild["after_hashes"],
            "rebuild_receipt": rebuild["receipt_file"],
        }

    def restore(self, revision_id: str, new_revision_id: str) -> dict[str, Any]:
        if not SAFE_SECTION_ID.fullmatch(revision_id):
            raise ContractError("revision_id is invalid")
        source_backup = self.revision_root / revision_id / "before" / self.source_path.relative_to(self.project_root)
        resolve_within(self.project_root, source_backup, "manuscript.restore.source", must_exist=True)
        before_hashes = self.hashes()
        backup = self._backup(new_revision_id, [self.source_path, self.pdf_path, self.word_path])
        candidate_file = self.revision_root / new_revision_id / "candidate" / self.source_path.name
        candidate_text = source_backup.read_text(encoding="utf-8-sig")
        _atomic_text(candidate_file, candidate_text)
        _atomic_text(self.source_path, candidate_text)
        try:
            rebuild = self.rebuild(new_revision_id, before_hashes)
        except Exception as exc:
            self._restore_backup(
                backup,
                [self.source_path, self.pdf_path, self.word_path],
                before_hashes,
            )
            if isinstance(exc, ManuscriptBuildError):
                exc.failed_candidate_file = str(candidate_file)
                exc.backup_directory = str(backup)
                raise
            raise ManuscriptBuildError(
                str(exc),
                failed_candidate_file=str(candidate_file),
                backup_directory=str(backup),
            ) from exc
        return {
            "revision_id": new_revision_id,
            "restored_from": revision_id,
            "backup_directory": str(backup),
            "before_hashes": before_hashes,
            "after_hashes": rebuild["after_hashes"],
            "rebuild_receipt": rebuild["receipt_file"],
        }

    def gate_freshness(self, invalidated_at_ns: int | None) -> dict[str, Any]:
        groups: dict[str, Any] = {}
        for name, declared in self.receipt_groups.items():
            receipts = []
            for relative in declared:
                path = resolve_within(self.project_root, relative, f"manuscript.receipt_groups.{name}")
                exists = path.is_file()
                fresh = bool(exists and (invalidated_at_ns is None or path.stat().st_mtime_ns > invalidated_at_ns))
                receipts.append({"path": str(path), "exists": exists, "fresh": fresh, "sha256": _sha256(path)})
            groups[name] = {
                "status": "valid" if receipts and all(item["fresh"] for item in receipts) else "invalidated",
                "receipts": receipts,
            }
        return groups

    def products_ready(self) -> bool:
        return bool(
            self.source_path.is_file()
            and (self.pdf_path.is_file() or not self.require_pdf)
            and (self.word_path.is_file() or not self.require_word)
        )
