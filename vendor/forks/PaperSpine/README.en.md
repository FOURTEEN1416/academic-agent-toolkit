<p align="center">
  <img src="website/assets/brand/paperspine-mark.svg" width="112" alt="PaperSpine Ridge Seal logo">
</p>

# PaperSpine

[English](README.en.md) | [中文](README.md)

[**PaperSpine 使用讲解视频（Bilibili）**](https://www.bilibili.com/video/BV1rjVa6ZEYu)

[**🌍 Community Stargazer Atlas · a public GitHub community signal**](https://wubing2023.github.io/PaperSpine/)

## PaperSpine5 release candidate

PaperSpine5 `0.3.0-rc.1` adds a five-stage, local-first research production workspace while preserving this repository's established V4 install and update identity. Start with the [English release page](https://wubing2023.github.io/PaperSpine/v5/en/): give the complete zero-to-install instruction to an AI, or choose the Codex, Claude Code, or DSH host package. The [GitHub prerelease](https://github.com/WUBING2023/PaperSpine/releases/tag/v0.3.0-rc.1) carries four byte-immutable ZIPs, SHA-256 checksums, a manifest, and validation evidence.

V5 is an explicit opt-in RC and does not replace V4's `dist/paperspine_version.json` update source. Update checks are disabled by default, and publishing the software never authorizes an external manuscript submission. See [`RELEASE-NOTES-v0.3.0-rc.1.md`](RELEASE-NOTES-v0.3.0-rc.1.md) and [`ROLLBACK.md`](ROLLBACK.md) for the exact scope, limitations, and rollback policy.


> PaperSpine is a contribution-first, reviewer-aware academic writing system for four hosts: Claude Code, Codex, OpenClaw, and Hermes CLI.

It is designed for writing tasks where the target format matters: journal papers, conference papers, course or technical reports, reviews, and competition papers. PaperSpine asks the agent to learn the target scene and strong examples first, confirm the paper's contribution with the user, design the manuscript unit by unit, and only then write or rebuild it — finally emitting LaTeX / PDF / Word.

V4 is no longer a suite of 12 flat worker skills. It is **one** orchestrator skill named `paper-spine`: all 12-stage routing lives inside `SKILL.md`, each stage reads the matching playbook under `references/`, and role information lives in `agents/`.

## Repository Layout

```text
PaperSpine/
  src/                          # single source of truth
    skill/
      SKILL.md                  # the one paper-spine orchestrator (12-stage routing)
      references/               # per-stage playbooks (40+)
      agents/                   # role cards (research, reviewer, etc.)
    scripts/                    # deterministic helpers and gate scripts
    adapters/                   # per-host adapters (claude / codex / hermes)
  dist/                         # generated from src/ by the sync (do not hand-edit)
    claude/skills/paper-spine/  # Claude Code single skill
    claude/commands/paperspine.md
    codex/skills/paper-spine/   # Codex single skill
    codex/prompts/paperspine.md
    openclaw/skills/paper-spine/ # OpenClaw single skill
    hermes/skills/academic-writing/paper-spine/  # Hermes CLI single skill
    paperspine_version.json     # version metadata (4.0.0)
  .claude-plugin/               # Claude Code plugin metadata
  install.ps1                   # Windows installer (thin wrapper)
  install.sh                    # macOS / Linux installer (thin wrapper)
  README.md
  README.en.md
```

`src/` is the single source of truth. `dist/` is fully generated from `src/skill` + `src/scripts` + `src/adapters` by the sync script `src/scripts/sync_local_installs.py`. Do not edit `dist/` directly.

## Quick Install

On Windows PowerShell:

```powershell
git clone https://github.com/WUBING2023/PaperSpine.git
cd PaperSpine
.\install.ps1
```

On macOS / Linux:

```bash
git clone https://github.com/WUBING2023/PaperSpine.git
cd PaperSpine
bash install.sh
```

Both `install.ps1` and `install.sh` are thin wrappers that delegate to `src/scripts/sync_local_installs.py`: the script first generates `dist/` from `src/`, then installs the same `paper-spine` skill into all four hosts. It is PowerShell 5.1-safe and **never writes settings.json** (fixes issue #3, where old installers could wipe settings.json).

Clean up legacy leftovers:

```powershell
.\install.ps1 -CleanLegacy
```

```bash
bash install.sh --clean-legacy
```

`-CleanLegacy` / `--clean-legacy` removes old PaperSpine folders and leftover `paper-spine-*` worker copies that caused duplicate discovery or missing skills. The installer writes the installed version to `~/.paperspine/install_state.json` and preserves `~/.paperspine/config.json`, including UI language preferences.

## The Four Hosts

The same `paper-spine` skill is installed into four hosts, never mixed:

| Host | Install location | Typical entry |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/paper-spine` + `~/.claude/commands/paperspine.md` | `/paperspine` command |
| Codex | `~/.codex/skills/paper-spine` + `~/.codex/prompts/paperspine.md` | `/paperspine` prompt |
| OpenClaw | `~/.openclaw/skills/paper-spine` | `paper-spine` |
| Hermes CLI | `~/AppData/Local/hermes/skills/academic-writing/paper-spine` | `paper-spine` |

The corresponding `dist/` sources are `dist/claude/skills`, `dist/claude/commands`, `dist/codex/skills`, `dist/openclaw/skills`, and `dist/hermes/skills/academic-writing`. Restart or reload the host after installing. Do not copy the whole repository into a `skills` folder — that is the main cause of duplicated or missing skills.

## The /paperspine Entry

In Claude Code and Codex, the preferred entry is:

```text
/paperspine
```

When `paper_rewriting_output/paper_spine_config.json` is missing, this entry automatically launches the external terminal intake UI to collect configuration instead of asking the user to hand-write JSON. The fallback is the Python wizard:

```powershell
python src/scripts/intake_wizard.py
```

The intake writes:

```text
paper_rewriting_output/paper_spine_config.json
paper_rewriting_output/paper_spine_config.md
```

OpenClaw and Hermes CLI have no slash entry; just invoke the `paper-spine` skill, and it will route through intake when config is missing.

## Claude Code Plugin Install

Claude Code can also use the plugin metadata in `.claude-plugin`:

```text
/plugin marketplace add https://github.com/WUBING2023/PaperSpine
/plugin install paper-spine
/reload-plugins
```

The plugin manifest points to the single `paper-spine` skill under `dist/claude/skills`.

## Main Workflow

PaperSpine has two equal first-class workflows:

1. **Rewrite Existing**: improve an existing manuscript without treating the task as simple polishing.
2. **Build From Materials**: build a manuscript or report from a folder containing notes, figures, PDFs, data summaries, partial drafts, and experiment descriptions.

Supported target scenes:

- `journal`: journal paper
- `conference`: conference paper
- `report_review`: course report, technical report, or review
- `competition`: competition paper or competition report

Research tiers:

- `flash`: 3 target-scene examples, 3 recent/high-quality same-field papers, and official requirements.
- `pro`: 6 target-scene examples, 6 recent/high-quality same-field papers, and official requirements.

Output language is `en` or `zh`. When English output is selected, `translation_package=zh` additionally generates a Chinese translation package and a final Chinese Word document.

## Methodology Upgrade (V4)

On top of the original motivation thread, V4 introduces three core rules enforced by gates. Motivation is still required (`confirmed_motivation.md`), but it now supports the contribution rather than being the top organizing unit.

1. **Contribution-First.** The manuscript's highest-priority organizing unit is the confirmed contribution. Do not begin substantive writing until `confirmed_contribution.md` exists. Gate: `contribution_check.py`.
2. **Results-as-Validation.** Each major Results subsection must validate at least one contribution promise; metric-only units with no contribution mapping are a failure, recorded in `results_validation.md`. Gate: `results_validation_check.py`.
3. **Reviewer-Aware.** Before claiming submission-ready, produce `reviewer_audit.md` (reviewer value map + objection register + editorial fit) from the three reviewer agents. Gate: `reviewer_audit_check.py`.

The Stage 12 Final Audit hard gate runs all three checks at once; do not declare the work complete while any of them fails.

## The 12-Stage Orchestration

The `paper-spine` orchestrator does not patch sentences directly. It routes stage by stage, with each stage reading a playbook under `references/`:

1. **Intake**: validate `paper_spine_config.json`.
2. **Research**: learn the target scene, local/specified references, and strong examples.
3. **Citation**: build a claim-level citation support bank.
4. **Motivation Confirmation**: stop for the user to confirm the controlling motivation (BLOCKED; never auto-select).
5. **Humanize** (optional): apply tier-specific AI-trace reduction.
6. **Writing / Drafting**: rewrite or build, producing blueprints and the rationale matrix first.
7. **Integrity Audit**: completeness audit before LaTeX assembly.
8. **LaTeX / PDF / Word**: produce and check LaTeX, compile PDF when possible, and emit Word.
9. **Submission Package** (optional): highlights, cover letter, and other submission materials.
10. **Translation Package** (optional): for English output, produce the `translation_zh/` package and a final Chinese Word file.
11. **Review Response** (optional): generate a reviewer response.
12. **Final Audit**: completion hard gate; complete only when all checks pass.

Every stage is a gate guarded by `progress_check.py --gate <stage>`; a failing gate routes back to that stage — no skipping, no hand-written missing artifacts. Historical names such as `paper-spine-research` are legacy aliases only, not user entry points.

## New V4 Capabilities

- **Stage gates + resume**: `progress_check.py` provides per-stage gates and supports `resume` from the first incomplete stage, instead of restarting from scratch.
- **Submission package**: `submission_check.py` validates highlights, cover letter, and other submission materials.
- **Review response**: `respond_check.py` helps generate a structured review response.
- **English citation verification**: `citation_verification_en.py` verifies citations in English manuscripts.
- **Deeper humanize**: `humanize_check.py` runs by `light` / `medium` / `heavy` tier and reports measured D1–D5 metrics, splitting required findings from advisory ones.

## Local Reference Reading

Reference collection is no longer network-only. The config field `reference_mode` controls how PaperSpine starts literature and example reading:

- `local_first`: default. Index reference materials from the current working folder first, then supplement from the web when needed.
- `specified_paths`: index only the folders/files listed in `reference_paths`, then supplement according to the task.
- `web`: use web collection when the user has no local reference materials.

Local reference paths are written into `paper_rewriting_output/reference_materials/source_index.md`. Helper script:

```powershell
python src/scripts/reference_inventory.py . --output-dir paper_rewriting_output --mode local_first
```

PaperSpine may read user-provided PDFs, downloaded papers, BibTeX/RIS files, templates, notes, and school or competition documents. It must not bypass paywalls or private database access.

## Citation Support Bank

The Citation stage creates `paper_rewriting_output/citation_support_bank.md`. This is separate from exemplar learning: exemplar papers teach structure and rhetoric; the citation support bank supplies candidate papers for Introduction, Related Work, Discussion, limitations, applications, and background claims.

Default behavior:

- `citation_target_count`: `20`
- candidate pool: `citation_target_count * 3`, so the default is `60`
- recent-paper target: about `80%` of candidates from the last three years (in 2026 the simple threshold is 2023 or later)
- each candidate row must include a reference/BibTeX-style entry, year, source, and one or two support sentences that can justify a manuscript statement

Check the bank with:

```powershell
python src/scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
```

## Key Artifacts

A complete run should leave a transparent, auditable trail, not just a final manuscript:

```text
paper_rewriting_output/
  paper_spine_config.json
  paper_spine_config.md
  reference_materials/source_index.md
  research_dossier.md
  exemplar_learning_dossier.md
  style_profile.md
  sota_gap_map.md
  motivation_options_after_research.md
  citation_support_bank.md
  confirmed_motivation.md
  confirmed_contribution.md       # V4 contribution-first
  results_validation.md           # V4 results-as-validation
  reviewer_audit.md               # V4 reviewer-aware
  section_blueprints.md
  writing_rationale_matrix.md
  latex_report.md
  final_artifact_manifest.md
  final_paper/
    main.tex
    references.bib
    figures/
    paper.pdf                     # generated when a LaTeX compiler is available
    paper.docx                    # English Word output
    paper.zh.docx                 # when output_language=zh or a translation package
  submission_package/             # when submission materials are requested
  review_response/                # when a review response is requested
  translation_zh/                 # when translation_package=zh
```

The central artifact is `writing_rationale_matrix.md`. It must explain the plan unit by unit: what the unit does, how it serves the confirmed contribution and motivation, what was learned from SOTA or target-scene examples, which evidence supports it, and what final text check should pass. `citation_support_bank.md` is the second major reasoning artifact: it makes every candidate citation traceable to a concrete sentence-level claim before it enters the manuscript.

## Quality Checks

Run the artifact checker:

```powershell
python src/scripts/artifact_check.py paper_rewriting_output --markdown --write
```

Stage gates and the methodology hard gates:

```powershell
python src/scripts/progress_check.py paper_rewriting_output --gate final_audit
python src/scripts/contribution_check.py paper_rewriting_output --markdown --write
python src/scripts/results_validation_check.py paper_rewriting_output --markdown --write
python src/scripts/reviewer_audit_check.py paper_rewriting_output --markdown --write
python src/scripts/integrity_audit.py paper_rewriting_output --markdown --write
```

Check LaTeX and Word:

```powershell
python src/scripts/latex_guard.py paper_rewriting_output/final_paper/main.tex --markdown
python src/scripts/word_guard.py paper_rewriting_output/final_paper/paper.docx --markdown
```

Check local reference indexing and citation candidate coverage:

```powershell
python src/scripts/reference_inventory.py . --output-dir paper_rewriting_output --mode local_first
python src/scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
```

Run repository tests:

```powershell
python -m pytest tests -q
```

## Updating PaperSpine

> ⚠️ **Upgrading from 3.x to 4.0 requires a manual reinstall — self-update does not apply.** 4.0 collapses the former 12 sub-skills into a single `paper-spine` orchestrator, so the 3.x updater rejects the new package as "missing 11 skills" and aborts. **Run the installer once, with `--clean-legacy`** (otherwise the old worker skills linger and hosts like cc switch show a mix of old and new):
>
> - Windows: `powershell -File install.ps1 -CleanLegacy`
> - macOS/Linux: `bash install.sh --clean-legacy`
>
> Afterwards `--check-only` reports `already latest: 4.0.0` and self-update works again. From 4.0 on the updater is forward-compatible and no longer aborts on things like a renamed doc.

After the first install, to check or update the local install, route `paper-spine` through its update path (`/paperspine update`), which runs:

```powershell
python src/scripts/paperspine_update.py --yes
```

It compares the version recorded in `~/.paperspine/install_state.json` with the GitHub `main` manifest at `dist/paperspine_version.json`. If the local copy is current, it reports that no update is needed; if a new version exists, it downloads the GitHub archive, validates the PaperSpine layout, updates the `paper-spine` skill across all four hosts, and keeps `~/.paperspine/config.json` intact. For a non-mutating check:

```powershell
python src/scripts/paperspine_update.py --check-only
```

**Still reporting "incomplete"?** Any old version self-updating to a newer one and reporting `Downloaded PaperSpine package is incomplete` hits the same cause: the **old validator rejects the new package** (the upgrade runs your *local, old* validator — issue #13). The manual reinstall above fixes it; you can also copy `dist/claude/skills/*` and `dist/claude/commands/paperspine.md` from `main` into `~/.claude/skills/` and `~/.claude/commands/`. From 4.0.0 on the updater only warns (never aborts) on optional files (README / installers), so this no longer recurs.

## What PaperSpine Tries To Prevent

- Polishing sentences without changing the paper's logic or contribution.
- Writing before confirming the contribution and motivation.
- Results that pile up metrics but validate no contribution promise.
- Claiming submission-ready without a reviewer-aware audit.
- Adding claims that are not supported by evidence.
- Producing only `main.tex` without explaining why the paper was written that way, and without Word output.
- Partial translation packages when the user requested translated intermediate artifacts.

## License

MIT License. See [LICENSE](LICENSE).

## Contributors

- [Wubin2023](https://github.com/WUBING2023) — Creator, core contributor, and maintainer of PaperSpine across V1–V4, leading its design, development, and continued evolution.
- [ZHOUYUNCHEN](https://github.com/ZHOUYUNCHEN) — Early V4 collaborator.
