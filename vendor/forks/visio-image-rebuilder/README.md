# visio-image-rebuilder

Codex skill for rebuilding reference images, screenshots, and existing diagrams into editable Microsoft Visio `.vsdx` files.

This skill is especially tuned for Chinese technical-bid flowcharts: repeated supervision, procurement, schedule, QA/QC, change-management, and similar engineering workflow diagrams.

## What It Does

- Rebuilds diagrams as native editable Visio shapes, text, and connectors.
- Avoids using a full-page embedded screenshot as the final output.
- Supports full figure reconstruction, style transfer, package inspection, and optional export to PNG/SVG/PDF/PPTX.
- Provides PowerShell/Visio COM helpers for repeatable native-shape drawing.
- Handles Chinese labels safely by using Unicode escapes in generated PowerShell scripts.

## Default Chinese Technical-Bid Mode

For Chinese technical-bid flowcharts, the default output is exactly one final `.vsdx` file.

Default style:

- Font: SimSun/宋体, 12 pt, not bold.
- Process boxes: straight-corner rectangles.
- Box fill: `RGB(198,216,240)`.
- Box border: `RGB(0,176,240)`, 1 pt.
- Connectors: `RGB(0,170,240)`, 1 pt.
- Arrowhead: Visio end arrow type `5` / `05`, medium size `2`.
- Page size: not larger than `165mm x 235mm` (`6.49in x 9.25in`), portrait or landscape.
- No backup file, preview image, SVG, PDF, or PPTX is created unless explicitly requested.
- Batch work uses simple sequential names such as `1.vsdx`, `2.vsdx`, `3.vsdx`, choosing the next unused number.

If the screenshot style conflicts with this default profile, the agent should ask whether to use the default technical-bid settings or reproduce the original image style.

## Repository Structure

```text
.
├── README.md
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── rebuild-guidelines.md
└── scripts/
    ├── visio_export_formats.ps1
    ├── visio_page_tools.ps1
    └── visio_rebuild_scaffold.ps1
```

## Requirements

- Windows.
- Microsoft Visio.
- PowerShell.
- Microsoft PowerPoint, only when PPTX export is requested.
- Codex or another agent environment that can run local PowerShell scripts.

Most rebuild work uses Visio COM automation, so the practical target environment is Windows with Microsoft Visio installed.

## Install

Clone this repository into your Codex skills directory:

```powershell
git clone https://github.com/ayuanyuan666-cpu/visio-image-rebuilder.git "$env:USERPROFILE\.codex\skills\visio-image-rebuilder"
```

Restart Codex or open a new session so the skill is rediscovered.

## Typical Usage

```text
使用 visio-image-rebuilder，把这张截图重建成可编辑 Visio 流程图，只需要最终 .vsdx。
```

```text
继续画这张，按默认技术标设置，输出 1 个 .vsdx，不要预览图。
```

```text
这个 .vsdx 按参考图改配色和布局，保留可编辑形状，并导出 PDF。
```

## Script Notes

`scripts/visio_rebuild_scaffold.ps1` is the primary starting point for custom rebuild scripts. It defaults to:

- `PageW = 9.25`
- `PageH = 6.49`
- VSDX-only output unless `-PreviewPath` or `-ExportFormats` is provided.
- No backup unless `-CreateBackup` is provided.

Fast VSDX-only example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\visio_rebuild_scaffold.ps1 `
  -VsdxPath "C:\path\outputs\1.vsdx" `
  -RefW 640 `
  -RefH 400
```

Multi-format export is opt-in:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\visio_rebuild_scaffold.ps1 `
  -VsdxPath "C:\path\outputs\figure.vsdx" `
  -PreviewPath "C:\path\outputs\figure.png" `
  -ExportFormats svg,pdf,pptx `
  -OutputDir "C:\path\outputs"
```

## Acceptance Criteria

- The final `.vsdx` uses native editable Visio shapes, text, and connectors.
- No full-page reference image remains in `visio/media`.
- Main hierarchy, labels, and connector topology match the reference.
- Chinese labels are preserved accurately.
- Fast technical-bid flowchart output creates only the final `.vsdx` unless more formats are requested.
