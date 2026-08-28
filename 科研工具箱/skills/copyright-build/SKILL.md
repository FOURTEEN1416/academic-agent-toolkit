---
name: copyright-build
description: >
  读取 copyright-draft 产出的草稿与门禁 JSON，调用成品脚本 build_docx_from_md.py
  生成正式的软件著作权申请资料 Word（代码材料、操作手册）和 TXT（申请表信息）。
  是"一句话生成软著申请资料"工作流的第二步（成品阶段）。
user-invocable: false
allowed-tools: >
  Bash, Read, Write, Edit, Glob, Grep
metadata:
  short-description: 生成软著正式 Word/TXT
  stage: build
---

# 软著申请资料 · 成品阶段（copyright-build）

上一步 `copyright-draft` 已经在 `软件著作权申请资料/草稿/` 下写好全部草稿和门禁 JSON，平台检查点也已让用户确认。本步骤只做一件事：调用成品脚本把草稿渲染成正式 Word/TXT。

如果 workspace 中存在 `source-materials/SOURCE_MATERIALS_MANIFEST.json`，先验证它的 backend 为 `vendored-codesucker-core` 且 audit 没有 fail。优先将 `source-materials/rendered/` 中的 DOCX/TXT 作为真实源码材料交付附件，并在 `正式资料/生成报告.md` 写入 core 版本、commit、规则版本、source mode、manifest 路径及所有 warning。不得用合成 Markdown 覆盖真实项目的标准流水线产物。

成品脚本路径通过环境变量 `$COPYRIGHT_SCRIPT_DIR` 注入（平台已把脚本复制到工作区并解密）。

## 生成正式资料

从 `草稿/申请表信息.md` 里读出软件全称和版本号（`➤软件全称：` 和 `➤版本号：` 两行的值），然后运行：

```bash
python3 "$COPYRIGHT_SCRIPT_DIR/build_docx_from_md.py" \
  --workdir 软件著作权申请资料 \
  --software-name "<软件全称>" \
  --version "<版本号>" \
  --skip-preview
```

说明：

- `--skip-preview` 跳过 vendor 的 OpenXML 预览校验（本工作流不带 vendor 工具，跳过即可）。
- 脚本会重新读取 `草稿/申请表信息.md` 的软件全称和版本号作为正式文件名与页眉的最终依据；命令行参数只作兜底。若两者不一致，脚本以申请表字段为准并在报告中记录。
- 脚本先执行门禁校验（`confirmation_issues`）：若任一草稿或门禁 JSON 缺失/未置真，会打印 `STOP_FOR_USER` 和缺失清单并以退出码 2 结束。此时回到上一步补齐草稿，不要绕过校验。

## 输出

成功后在 `软件著作权申请资料/正式资料/` 下生成：

- `申请表信息.txt`
- 代码 ≥60 页：`<软件全称>-代码(前30页).docx` + `<软件全称>-代码(后30页).docx`
- 代码 <60 页：`<软件全称>-代码(全部).docx`
- `<软件全称>_操作手册.docx`
- `生成报告.md`（含输出清单、警告、校验说明）

## 完成校验

运行后确认脚本输出以 `OK final materials:` 开头，并检查 `正式资料/` 下的 Word/TXT 均存在且非空。读一下 `正式资料/生成报告.md` 的警告段，如有"软件名称/版本号不一致"或"截图未插入"等提示，如实转达给用户。正式资料生成完成后，向用户汇报输出文件清单和存放位置。

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：素材来源、渲染引擎版本、截图方式。
