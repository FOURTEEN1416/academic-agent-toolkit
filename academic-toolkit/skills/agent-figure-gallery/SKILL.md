---
name: agent-figure-gallery
description: "Query visual scientific figure references, show candidates for human preference selection, export selected reference"
---

# Agent Figure Gallery

## Core Rule

Treat this skill as a lightweight controller. Do not load the full visual corpus into the skill. Use `AGENT_FIGURE_GALLERY_ROOT` or `DRAWING_KB_ROOT` to point at the external AgentFigureGallery knowledge base.

## Key Files

- KB root: `AGENT_FIGURE_GALLERY_ROOT=/path/to/AgentFigureGallery`
- CLI: `agentfiguregallery` or `python -m agentfiguregallery.cli`
- Gallery server: backend command that serves the reference gallery on localhost
- Candidate index: `data/reference_candidate_index.json`
- Global preferences: `data/reference_global_preferences.json`
- Reference sessions: `outputs/reference_sessions/`
- 本地构图参照索引（tracked）：`references/composition-index.json` — Origin 19 类图型图集
  （04/06 号批次，本地图集 gitignored）；按 plot_type 定位构图参照，默认配色不吸收。

## Loading the KB from a Local Source (pip-free, 2026-09-22)

The KB data body ships as a repo-local vendor snapshot at
`vendor/forks/AgentFigureGallery` (pin and license: see `UPSTREAM.md` beside this
file). The data is local-only and not redistributable; the vendor tree is
read-only — never modify or delete anything under `vendor/`.

Two equivalent host-neutral entry points:

1. Read-only search via the controller script (recommended first step; no install):
   ```bash
   python skills/agent-figure-gallery/scripts/kb_search.py \
     --task "<user task>" [--plot-type <type>] [--limit N] [--json]
   ```
   KB root resolution order: `$AGENT_FIGURE_GALLERY_ROOT` → `$DRAWING_KB_ROOT` →
   repo-local `vendor/forks/AgentFigureGallery` (derived relatively from the script
   location). If no root is found the script prints a `TOOL_GAP:` report listing
   the paths checked and exits 2 — it never crashes.
2. Upstream CLI without pip install (run from the KB root so the package resolves):
   ```bash
   cd vendor/forks/AgentFigureGallery
   python -m agentfiguregallery.cli doctor
   python -m agentfiguregallery.cli query --task "<user task>"
   ```

## Worked Example (real data, 2026-09-22)

Requirement: "t-SNE embedding clusters for a cell atlas".

```bash
python skills/agent-figure-gallery/scripts/kb_search.py \
  --task "t-SNE embedding clusters for cell atlas" --limit 3
```

Result (excerpt; all 284 candidates loaded, plot type auto-resolved to `embedding_plot`):

```json
{
  "kb_root": "vendor/forks/AgentFigureGallery",
  "index_source": "vendor/forks/AgentFigureGallery/data/reference_candidate_index.json",
  "resolved_plot_type": "embedding_plot",
  "total_candidates": 284,
  "results": [
    {
      "candidate_id": "EMB-F13BC81C31",
      "plot_type": "embedding_plot",
      "source_repo": "berenslab/mini-atlas",
      "quality_score": 80.0,
      "script_path": "repos/berenslab__mini-atlas/code/phenotype-tsne.ipynb",
      "why_suggested": "style_template script in code/phenotype-tsne.ipynb using matplotlib, seaborn.",
      "preview_path": "assets/packs/minimal/previews/embedding_plot/EMB-F13BC81C31.png"
    }
  ]
}
```

ACAT-GOVERNANCE：上例 `preview_path`/`script_path` 为 KB 根内相对路径
（KB 根 = `vendor/forks/AgentFigureGallery`），非本技能内部文件，勿按技能目录解析。
Provenance：条目出自上述 vendor 快照的 `data/reference_candidate_index.json`；
预览 PNG 实存于
`vendor/forks/AgentFigureGallery/assets/packs/minimal/previews/embedding_plot/EMB-F13BC81C31.png`
（摘录时字段顺序与斜杠按文档习惯调整，实跑输出为反斜杠混合路径）。

## Minimal Workflow (full upstream CLI, requires the KB root on path)

1. Resolve the KB root:
   ```bash
   export AGENT_FIGURE_GALLERY_ROOT=/path/to/AgentFigureGallery
   ```
2. Query before reading individual references:
   ```bash
   agentfiguregallery query --task "<user task>"
   ```
3. Generate visible candidates:
   ```bash
   agentfiguregallery gallery --plot-type <plot_type> --task "<user task>" --limit 50 --serve
   ```
4. Record human preferences:
   ```bash
   agentfiguregallery prefer --session outputs/reference_sessions/<session_id> --like <ID> --reject <ID> --select <ID>
   ```
5. Export a selected bundle:
   ```bash
   agentfiguregallery bundle --session outputs/reference_sessions/<session_id> --copy-scripts
   ```
6. Use the bundle before writing or revising plotting code.

## Preference Semantics

- `like`: useful for this task or plot type.
- `reject`: not useful for this task or plot type.
- `select`: use this candidate for the current agent action.
- `global_like`: generally useful across tasks.
- `global_reject`: hide from future sessions.

Local preferences must preserve `plot_type`. Global preferences are cross-task.

## Validation

After changing the CLI, gallery, preference logic, or bundle export:

```bash
agentfiguregallery gallery --plot-type embedding_plot --limit 20 --serve
agentfiguregallery prefer --session outputs/reference_sessions/<session_id> --like E01 --select E02
agentfiguregallery bundle --session outputs/reference_sessions/<session_id>
```

Success means visible candidates render, stable IDs are shown, preferences persist, global rejects are hidden from later generated sessions, and the bundle contains selected references plus source code paths.
