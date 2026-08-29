---
name: graphviz
description: Create directed/undirected graphs using DOT language with automatic layout. Best for dependency trees, call graphs, package hierarchies, and module relationships requiring fine-grained edge routing.
metadata:
  author: Graphviz is powered by Markdown Viewer — the best multi-platform Markdown extension (Chrome/Edge/Firefox/VS Code) with diagrams, formulas, and one-click Word export. Learn more at https://docu.md
---

# Graphviz DOT Diagram Generator

> **Important:** Use ` ```dot ` as the code fence identifier, NOT ` ```graphviz `.

**Quick Start:** Choose `digraph` (directed) or `graph` (undirected) → Define nodes with attributes (shape, color, label) → Connect with `->` or `--` → Set layout (rankdir, spacing) → Wrap in ` ```dot ` fence. Default: top-to-bottom (`rankdir=TB`), cluster names must start with `cluster_`, use semicolons.

---

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：DOT 源文件与 graphviz 版本（dot -V）。图表溯源门禁 figure_provenance 要求图有来源证据。

## Critical Syntax Rules

### Rule 1: Cluster Naming
```
❌ subgraph backend { }      → Won't render as box
✅ subgraph cluster_backend { }  → Must start with cluster_
```

### Rule 2: Node IDs with Spaces
```
❌ API Gateway [label="API"];    → Invalid ID
✅ "API Gateway" [label="API"];  → Quote the ID
✅ api_gateway [label="API Gateway"];  → Use underscore ID
```

### Rule 3: Edge Syntax Difference
```
digraph: A -> B;   → Directed arrow
graph:   A -- B;   → Undirected line
```

### Rule 4: Attribute Syntax
```
❌ node [shape=box color=red]    → Missing comma
✅ node [shape=box, color=red];  → Comma separated
```

### Rule 5: HTML Labels
```
✅ shape=plaintext for HTML labels
✅ Use < > not " " for HTML content
```

---

## Common Pitfalls

| Issue | Solution |
|-------|----------|
| Nodes overlapping | Increase `nodesep` and `ranksep` |
| Poor layout | Change `rankdir` or add `{rank=same}` |
| Edges crossing | Use `splines=ortho` or adjust node order |
| Cluster not showing | Name must start with `cluster_` |
| Label not displaying | Check quote escaping |

---

## Output Format

````markdown
```dot
digraph G {
    [diagram code]
}
```
````

---

## Related Files

> For advanced layout control and complex styling, refer to references below:

- [syntax.md](references/syntax.md) — Layout control (rankdir, splines, rank), HTML labels, edge styles, cluster subgraphs, and record-based nodes
