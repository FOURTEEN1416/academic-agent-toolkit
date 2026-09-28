# Recommended Repo Structure（建议目录结构）

```text
project/
  manuscript/
    main.tex              # 或 main.docx / index.qmd（任选其一）
    refs.bib
    sections/
  figures/
    fig-01/
      src/
        plot.py
      data/
      out/
        fig-01.pdf
        fig-01.tiff
      README.md           # 说明：数据来源/参数/导出命令
    fig-02/
      ...
  supplement/
    supplement.tex
  submission/
    cover-letter.md
    highlights.md
    submission-manifest.yml
  revision/
    rebuttal.md
    rebuttal-response-matrix.md
  build/
    manuscript.pdf
    submission.zip
  scripts/
    build.sh / build.ps1
    export_figures.py
  README.md
```

## 约束

- `build/` 可随时删除并重生成
- `figures/**/out/` 只存最终导出，不做手工编辑
- `figures/**/README.md` 必须写清楚“如何重生成”

