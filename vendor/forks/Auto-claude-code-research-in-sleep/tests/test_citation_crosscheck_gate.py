"""CI guard for the /citation-crosscheck deterministic verifier gate (cx_verify.py).

cx_verify.py is a load-bearing gate: it decides which citations reach MATCH/MINOR without a
main-agent fetch. Its correctness is covered by an in-script ``--selftest`` battery, and the
skill ships two byte-identical host copies (Claude Code mainline + Codex mirror). This test
runs both — pre-merge, in the normal ``pytest tests/`` suite — so a regression in the gate or a
drift between the two copies fails CI instead of being discovered on a live run.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_GATE = REPO_ROOT / "skills" / "citation-crosscheck" / "scripts" / "cx_verify.py"
CODEX_GATE = REPO_ROOT / "skills" / "skills-codex" / "citation-crosscheck" / "scripts" / "cx_verify.py"


def test_gate_scripts_exist() -> None:
    assert MAIN_GATE.is_file(), f"missing {MAIN_GATE}"
    assert CODEX_GATE.is_file(), f"missing {CODEX_GATE}"


def test_mirror_copies_are_byte_identical() -> None:
    # A fix applied to one host copy must be applied to the other, verbatim; otherwise the
    # two hosts silently run different gates.
    assert MAIN_GATE.read_bytes() == CODEX_GATE.read_bytes(), (
        "cx_verify.py mainline and Codex-mirror copies differ — re-sync them byte-for-byte "
        "(cp skills/citation-crosscheck/scripts/cx_verify.py "
        "skills/skills-codex/citation-crosscheck/scripts/cx_verify.py)"
    )


def _run_selftest(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path), "--selftest"],
        capture_output=True,
        text=True,
    )


def test_selftest_passes_mainline() -> None:
    result = _run_selftest(MAIN_GATE)
    assert result.returncode == 0, (
        f"cx_verify.py --selftest failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    # Require an "N/N passed" summary (all cases), not just the substring "passed" — a
    # partial-failure run prints e.g. "94/107 passed" and must not read as success.
    assert re.search(r"\b(\d+)/\1 passed\b", result.stdout), result.stdout


def test_selftest_passes_codex_mirror() -> None:
    result = _run_selftest(CODEX_GATE)
    assert result.returncode == 0, (
        f"Codex-mirror cx_verify.py --selftest failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    # Require an "N/N passed" summary (all cases), not just the substring "passed" — a
    # partial-failure run prints e.g. "94/107 passed" and must not read as success.
    assert re.search(r"\b(\d+)/\1 passed\b", result.stdout), result.stdout


def test_manifest_cli_covers_the_documented_workflow(tmp_path: Path) -> None:
    """Build the coverage root from a real .bib, then run the A/B/C gate."""
    record = "@article{paper, title={Deep Nets}, author={Smith, Alice}, year={2020}, journal={ICML}, doi={10.1/example}}"
    bib = tmp_path / "refs.bib"
    bib.write_text(record, encoding="utf-8")
    keymap = tmp_path / "keymap.tsv"
    keymap.write_text("01\tpaper\n", encoding="utf-8")
    manifest = tmp_path / "manifest.tsv"
    built = subprocess.run(
        [sys.executable, str(MAIN_GATE), "--build-manifest", "--bib", str(bib),
         "--keymap", str(keymap), "--out-manifest", str(manifest)],
        capture_output=True, text=True,
    )
    assert built.returncode == 0, built.stderr
    a = {"shard_id": "A", "entries": [{"dedup_key": "01", "key": "paper", "bibtex": record}]}
    b = {"shard_id": "B", "blind": True, "entries": [{"dedup_key": "01", "found": True,
         "bibtex": record, "sources_tried": ["crossref"]}]}
    c = {"shard_id": "C", "entries": [{"dedup_key": "01", "flags": []}]}
    paths = [tmp_path / f"{label}.json" for label in ("a", "b", "c")]
    output = tmp_path / "gate.json"

    def run_gate():
        for path, value in zip(paths, (a, b, c)):
            path.write_text(json.dumps(value), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(MAIN_GATE), "--a", str(paths[0]), "--b", str(paths[1]),
             "--c", str(paths[2]), "--expect", "1", "--expect-manifest", str(manifest),
             "--json", str(output)], capture_output=True, text=True,
        )

    clean = run_gate()
    assert clean.returncode == 0, clean.stderr
    assert json.loads(output.read_text())["counts"] == {"MATCH": 1, "MINOR": 0, "ESCALATE": 0}

    b["blind"] = False
    heuristic = run_gate()
    assert heuristic.returncode == 0, heuristic.stderr
    assert json.loads(output.read_text())["entries"][0]["verdict"] == "ESCALATE"

    b["blind"] = True
    b["entries"][0]["sources_tried"] = ["crossref(429)"]
    degraded = run_gate()
    assert degraded.returncode == 0, degraded.stderr
    assert json.loads(output.read_text())["entries"][0]["verdict"] == "ESCALATE"

    # A keeps the same ordinal and title but substitutes another cite key.
    a["entries"][0]["key"] = "substituted"
    substituted = run_gate()
    assert substituted.returncode == 1
    assert "coverage manifest mismatch" in substituted.stderr


@pytest.mark.parametrize("surname", ["Jr", "Sr", "Ii", "III", "IV"])
@pytest.mark.parametrize("given", ["Naosuke", "Naosuke Middle"])
def test_suffix_token_surnames_survive_normalization(surname: str, given: str) -> None:
    spec = importlib.util.spec_from_file_location("citation_gate", MAIN_GATE)
    assert spec and spec.loader
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    def verdict(ours: str, web: str) -> str:
        return gate.classify(gate._entry(*gate._both(authors=ours, web_authors=web)))[0]

    # The actual surname is neither erased nor mistaken for the given name.
    assert verdict(f"Alice Smith and {given} {surname}", f"Alice Smith and {given}") == "ESCALATE"
    assert verdict(f"{surname}, {given}", f"{given} {surname}") == "MATCH"
    assert verdict(f"{given} {surname}", f"{surname}, {given}") == "MATCH"


@pytest.mark.parametrize(
    ("mapping", "kept", "error"),
    [
        ([("01", "paperA"), ("02", "paperB"), ("02", "paperC")],
         [("01", "paperA"), ("02", "paperC")], "duplicate dedup_key"),
        ([("01", "paperA"), ("02", "paperC"), ("02", "paperC")],
         [("01", "paperA"), ("02", "paperC")], "duplicate dedup_key"),
        ([("01", "paperA"), ("02", "paperA"), ("03", "paperC")],
         [("01", "paperA"), ("02", "paperA"), ("03", "paperC")], "duplicate cite key"),
    ],
)
def test_manifest_rejects_duplicate_coverage_at_build_and_load(
    tmp_path: Path, mapping: list, kept: list, error: str,
) -> None:
    records = {
        key: f"@article{{{key}, title={{{key}}}, author={{Smith, Alice}}, year={{2020}}, journal={{ICML}}, doi={{10.1/example}}}}"
        for key in ("paperA", "paperB", "paperC")
    }
    bib = tmp_path / "refs.bib"
    bib.write_text("\n".join(records.values()), encoding="utf-8")
    keymap, manifest = tmp_path / "keymap.tsv", tmp_path / "manifest.tsv"
    build_cmd = [sys.executable, str(MAIN_GATE), "--build-manifest", "--bib", str(bib),
                 "--keymap", str(keymap), "--out-manifest", str(manifest)]
    keymap.write_text("".join(f"{dk}\t{key}\n" for dk, key in mapping), encoding="utf-8")
    bad_build = subprocess.run(build_cmd, capture_output=True, text=True)
    assert bad_build.returncode == 1
    assert error in bad_build.stderr
    assert not manifest.exists()

    # Generate correct title hashes, then inject the same duplicate into a manifest
    # supplied directly to the verifier. The old loader silently kept the last row.
    keymap.write_text("01\tpaperA\n02\tpaperB\n03\tpaperC\n", encoding="utf-8")
    clean_build = subprocess.run(build_cmd, capture_output=True, text=True)
    assert clean_build.returncode == 0, clean_build.stderr
    hashes = {row.split("\t")[1]: row.split("\t")[2] for row in manifest.read_text().splitlines()}
    manifest.write_text("".join(f"{dk}\t{key}\t{hashes[key]}\n" for dk, key in mapping), encoding="utf-8")
    shards = {
        "a": {"entries": [{"dedup_key": dk, "key": key, "bibtex": records[key]} for dk, key in kept]},
        "b": {"blind": True, "entries": [{"dedup_key": dk, "found": True, "bibtex": records[key],
                                            "sources_tried": ["crossref"]} for dk, key in kept]},
        "c": {"entries": [{"dedup_key": dk, "flags": []} for dk, key in kept]},
    }
    for side, value in shards.items():
        (tmp_path / f"{side}.json").write_text(json.dumps(value), encoding="utf-8")
    expected_keys = tmp_path / "expected.txt"
    expected_keys.write_text("\n".join(dk for dk, _ in kept), encoding="utf-8")
    checked = subprocess.run(
        [sys.executable, str(MAIN_GATE), "--a", str(tmp_path / "a.json"),
         "--b", str(tmp_path / "b.json"), "--c", str(tmp_path / "c.json"),
         "--expect", str(len(kept)), "--expect-keys", str(expected_keys),
         "--expect-manifest", str(manifest)], capture_output=True, text=True,
    )
    assert checked.returncode == 1
    assert error in checked.stderr
    assert "MATCH=2" not in checked.stdout


@pytest.mark.parametrize("skill_root", [MAIN_GATE.parents[1], CODEX_GATE.parents[1]])
def test_step_one_harvests_sentence_initial_biblatex_cite(tmp_path: Path, skill_root: Path) -> None:
    source = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    step_one = source.split("### Step 1", 1)[1]
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY", step_one, re.S)
    assert match, "Step 1's actual citation-harvest script is missing"
    # Keep the actual harvest logic; redirect its shared /tmp outputs for this test.
    script = match.group(1).replace("/tmp/cx_", str(tmp_path / "cx_"))
    (tmp_path / "main.tex").write_text(
        "\\Cite{sentence}\n\\cite{lower}\n% \\Cite{commented}\n", encoding="utf-8",
    )
    harvested = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True,
    )
    assert harvested.returncode == 0, harvested.stderr
    assert set((tmp_path / "cx_cited_keys.txt").read_text().splitlines()) == {"sentence", "lower"}
    assert "CITED_KEY_COUNT=2" in harvested.stdout
