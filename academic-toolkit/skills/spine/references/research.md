# Research Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Learn the target scene, index local references, study strong examples, map SOTA
gaps, and produce user-confirmable motivation options. Research must complete
before the user confirms the controlling motivation.

## Literature Retrieval Priority Protocol

1. **Literature MCP tools (preferred).** If the host has MCP servers matching
   `cnki`, `ieee`, `arxiv`, `semantic scholar`, `scholar`, `pubmed`, `crossref`,
   `wos`, `web of science`, or `scopus`, use them first. Record the source
   channel in `source_index.md` as `MCP-CNKI`, `MCP-IEEE`, `MCP-PubMed`, etc.
2. **Host WebSearch / browsing tools (fallback).**
3. **Local files (always available).**
4. **local_first rule:** when `reference_mode=local_first` or `specified_paths`,
   local index must be built first; MCP/web may supplement only.
5. **MCP is an enhancement, not a dependency.** Do not error or ask the user to
   install MCP when none is available.

## Tier Rules

- `flash`: 3 target-scene examples + 3 recent high-quality field/SOTA examples.
- `pro`: 6 target-scene examples + 6 recent high-quality field/SOTA examples.

## Stage 1 — Index Local References

Create `paper_rewriting_output/reference_materials/source_index.md`:

| Source ID | Type | Title/Name | Origin/URL/Path | Why Included | Local File/Note | Used For |
|---|---|---|---|---|---|---|

Use `scripts/reference_inventory.py`:
```bash
python scripts/reference_inventory.py . --output-dir paper_rewriting_output --mode local_first
```

## Stage 2 — Three Parallel Specialist Sub-Agents

Launch all three simultaneously. Each agent gets only its own context.

### Agent A: Scene Analyst → `research_dossier.md`

Context: `scene`, `target_name`, `official_urls`, `source_index.md`, scene reference file.

Sections: Venue Requirements, Review Criteria, Accepted Paper Patterns, Constraints for This Paper.

### Agent B: Exemplar Learner → `exemplar_learning_dossier.md`

Context: `tier`, `source_index.md`, scene reference path.

Sections: Exemplar Inventory table, Structural Patterns, Rhetorical Patterns, Language Patterns.

### Agent C: SOTA Mapper → `sota_gap_map.md`

Context: `tier`, `source_index.md`, `user_motivation` (if set).

Table: Candidate Contribution | What SOTA Already Does | User Evidence | Real Gap | Claim Strength | Risk. Plus Gap Summary.

## Stage 3 — Merge

Produce `style_profile.md` and `motivation_options_after_research.md`. Stop for
user confirmation. Write `confirmed_motivation.md` only after the user chooses,
revises, or writes their own motivation.

## Required Outputs

- `reference_materials/source_index.md`
- `research_dossier.md`
- `exemplar_learning_dossier.md`
- `style_profile.md`
- `sota_gap_map.md`
- `motivation_options_after_research.md`
- `confirmed_motivation.md` (after user confirmation)
