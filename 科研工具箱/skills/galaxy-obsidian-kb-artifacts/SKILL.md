---
name: obsidian-kb-artifacts
description: Use this skill for Obsidian-native formatting and derived artifacts such as Markdown formatting, wikilinks, registry tables, canvas files, optional Bases, CLI operations, and link repair. This skill does not decide knowledge routing.
---

# Obsidian KB Artifacts

This skill handles format and artifact concerns only.

## Responsibilities

- Obsidian Markdown formatting
- wikilinks and embeds
- registry table formatting
- canvas generation and validation
- optional Bases generation
- Obsidian CLI operations
- link repair in canonical notes
- lint-report formatting

## Rules

- this skill does not decide where knowledge belongs
- `.base` is explicit-only
- `Maps/` contains derived artifacts only
- link repair should strengthen existing canonical notes, not create note sprawl
- literature canvas edges must preserve evidence strength when the source notes provide it
- do not create stable-looking claim edges from abstract-only, webpage-placeholder, or unsupported notes

## Read next

- `references/OBSIDIAN-MARKDOWN.md`
- `references/CANVAS.md`
- `references/BASES.md`
- `references/REGISTRY-TABLES.md`
- `references/LINK-REPAIR.md`
- `references/CLI.md`
